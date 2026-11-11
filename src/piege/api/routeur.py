"""Piège — routeur HTTP de l'API (bibliothèque standard uniquement).

Règle de sécurité structurante (EF-61) : **aucune route n'accepte un tenant en
paramètre**. Le tenant vient du jeton, résolu une fois par requête, et toute
requête portant un tenant dans son corps est refusée avant d'atteindre un
gestionnaire.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from piege.api.contexte import Api
from piege.erreurs import ErreurPiege, TenantInconnu
from piege.securite.identite import (refuser_tenant_en_parametre, resoudre_tenant,
                                     roles)

__all__ = ["router", "Route", "ROUTES", "correspondance", "identite"]

Route = tuple[str, str, Callable]


def identite(entetes: Optional[dict]) -> tuple[str, list[str]]:
    """Résout (tenant, rôles) depuis l'en-tête d'authentification."""
    entetes = {str(k).lower(): v for k, v in (entetes or {}).items()}
    brut = entetes.get("authorization", "")
    jeton = brut[7:].strip() if brut.lower().startswith("bearer ") else brut.strip()
    if not jeton:
        raise TenantInconnu("jeton d'authentification absent",
                            code="tenant_inconnu",
                            details={"regle": "identite.jeton"})
    return resoudre_tenant(jeton), roles(jeton)


def correspondance(motif: str, chemin: str) -> Optional[dict]:
    """Fait correspondre un motif de route à un chemin ; rend les paramètres."""
    regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", motif.rstrip("/")) + "/?$"
    trouve = re.match("^" + regex, chemin.rstrip("/") + "/")
    return trouve.groupdict() if trouve else None


def router(methode: str, chemin: str, corps: Optional[dict] = None,
           entetes: Optional[dict] = None, api: Optional[Api] = None) -> tuple[int, dict]:
    """Aiguille une requête ; rend (statut HTTP, corps JSON)."""
    from piege.api import ressources

    api = api or Api()
    methode = (methode or "GET").upper()
    chemin, requete = _separer_requete(chemin)
    try:
        tenant, liste_roles = identite(entetes)
        refuser_tenant_en_parametre(corps or {})
        refuser_tenant_en_parametre(requete)
        for route_methode, motif, gestionnaire in ressources.ROUTES:
            if route_methode != methode:
                continue
            parametres = correspondance(motif, chemin)
            if parametres is None:
                continue
            return _appeler(gestionnaire, api, tenant, liste_roles, corps or {},
                            parametres, requete)
        return 404, {"erreur": {"code": "route_inconnue",
                                "message": "%s %s" % (methode, chemin),
                                "regle": "api.route"}}
    except ErreurPiege as erreur:
        return erreur.statut_http, erreur.vers_dict()
    except (ValueError, KeyError, TypeError) as erreur:
        return 400, {"erreur": {"code": "requete_invalide",
                                "message": str(erreur)[:200], "regle": "api.corps"}}


def _separer_requete(chemin: str) -> tuple[str, dict]:
    """Sépare le chemin de sa chaîne de requête (valeurs simples)."""
    from urllib.parse import parse_qs, urlsplit

    parties = urlsplit(chemin or "/")
    requete = {cle: valeurs[0] for cle, valeurs in parse_qs(parties.query).items()}
    return parties.path or "/", requete


def _appeler(gestionnaire: Callable, api: Any, tenant: str, liste_roles: list,
             corps: dict, parametres: dict, requete: Optional[dict] = None) -> tuple:
    """Appelle un gestionnaire avec le contexte d'identité résolu."""
    resultat = gestionnaire(api=api, tenant=tenant, roles=liste_roles,
                            corps=corps, requete=dict(requete or {}), **parametres)
    if isinstance(resultat, tuple):
        return resultat
    return 200, {"donnees": resultat}
