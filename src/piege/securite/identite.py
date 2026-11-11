"""Piège — identité : le tenant vient du jeton, jamais du texte libre.

Aucune route n'accepte un tenant en paramètre (EF-61) : l'isolation est imposée
par l'identité, pas par l'interface (ENF-06, spécification §21.4). En mode hors
ligne, le jeton est une convention de test explicite — `jeton:<tenant>:<role>` —
documentée comme telle et jamais utilisée en production.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege.erreurs import TenantInconnu

__all__ = ["ROLES", "resoudre_tenant", "roles", "exiger_role", "jeton_test",
           "refuser_tenant_en_parametre", "PREFIXE_TEST"]

ROLES = ("commanditaire", "proprietaire", "analyste", "commercial")
PREFIXE_TEST = "jeton:"
PARAMETRES_INTERDITS = ("tenant", "tenant_id", "client", "client_id")


def _decouper(jeton: str) -> list[str]:
    """Découpe un jeton hors ligne ; lève `TenantInconnu` s'il est malformé."""
    if not jeton or not isinstance(jeton, str):
        raise TenantInconnu("jeton absent : identité de tenant indéterminable",
                            details={"regle": "identite.jeton"})
    if not jeton.startswith(PREFIXE_TEST):
        raise TenantInconnu("jeton hors ligne malformé (préfixe %s attendu)"
                            % PREFIXE_TEST, details={"regle": "identite.format"})
    morceaux = [m for m in jeton[len(PREFIXE_TEST):].split(":") if m]
    if len(morceaux) < 2:
        raise TenantInconnu("jeton hors ligne incomplet : tenant et rôle requis",
                            details={"regle": "identite.format"})
    return morceaux


def resoudre_tenant(jeton: str) -> str:
    """Retourne l'identifiant de tenant porté par le jeton (EF-61)."""
    return _decouper(jeton)[0]


def roles(jeton: str) -> list[str]:
    """Rôles portés par le jeton, dans l'ordre déclaré."""
    return _decouper(jeton)[1:]


def exiger_role(tenant: str, jeton: str, roles_autorises: Iterable[str]) -> None:
    """Vérifie que le jeton porte le bon tenant et un rôle habilité."""
    if resoudre_tenant(jeton) != tenant:
        raise TenantInconnu("le jeton ne porte pas le tenant de la ressource",
                            details={"regle": "identite.tenant"})
    autorises = set(roles_autorises)
    if not autorises.intersection(roles(jeton)):
        raise TenantInconnu("aucun rôle habilité (%s) dans le jeton"
                            % ", ".join(sorted(autorises)),
                            details={"regle": "identite.role"})


def jeton_test(tenant: str, *roles_du_jet: str) -> str:
    """Fabrique un jeton hors ligne (convention de test uniquement)."""
    declares = list(roles_du_jet) or ["analyste"]
    inconnus = [r for r in declares if r not in ROLES]
    if inconnus:
        raise TenantInconnu("rôle(s) inconnu(s) : %s" % ", ".join(inconnus),
                            details={"regle": "identite.role"})
    return PREFIXE_TEST + ":".join([tenant] + declares)


def refuser_tenant_en_parametre(parametres: Optional[dict]) -> None:
    """Refuse toute requête qui porte un tenant en paramètre (EF-61)."""
    if not parametres:
        return
    trouves = [cle for cle in parametres if cle in PARAMETRES_INTERDITS]
    if trouves:
        raise TenantInconnu(
            "le tenant ne se transmet jamais en paramètre (%s) : il vient du "
            "jeton" % ", ".join(trouves), details={"regle": "identite.parametre"})
