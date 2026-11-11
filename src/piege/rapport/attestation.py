"""Piège — attestation destinée à un tiers (EF-53, recette R16).

Une attestation s'adresse à un assureur, un donneur d'ordre ou un auditeur :
elle dit **que** le test a eu lieu, dans quel périmètre, et quel en est le
résultat agrégé. Elle ne contient volontairement ni sonde, ni citation, ni
détail exploitable : publiée, elle ne doit aider personne à attaquer
l'application.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege.rapport.traductions import traduire
from piege.types import Campagne, Finding, Severite, maintenant_utc

__all__ = ["attestation", "compte_severites"]


def compte_severites(findings: Iterable) -> dict:
    """Décompte des découvertes par classe de sévérité."""
    compte = {severite.value: 0 for severite in Severite}
    for brut in findings:
        valeur = brut.get("severite") if isinstance(brut, dict) else brut.severite
        cle = valeur.value if hasattr(valeur, "value") else str(valeur)
        compte[cle] = compte.get(cle, 0) + 1
    return compte


def attestation(campagne: Campagne, findings: list, langue: str = "fr",
                destinataire: str = "", mandat_ref: Optional[str] = None) -> str:
    """Attestation datée, pauvre en détails, prête à signer."""
    t = lambda cle: traduire(cle, langue)                     # noqa: E731
    compte = compte_severites(findings or [])
    fermes = _compte_fermes(findings or [])
    lignes = [
        "# %s" % t("titre_attestation"),
        "",
        t("attestation_corps"),
        "",
        "- **%s** : %s" % (t("campagne"), campagne.id),
        "- **%s** : %s" % (t("application"), campagne.application_id),
        "- **%s** : %s" % (t("mandat"), mandat_ref or campagne.mandat_id),
        "- **%s** : %s" % (t("date"), campagne.terminee_le or maintenant_utc()),
        "- **%s** : %s" % (t("graine"), campagne.graine),
    ]
    if destinataire:
        lignes.append("- **Destinataire** : %s" % destinataire)
    lignes += ["", "## %s" % t("synthese"), "", _bloc_chiffres(compte, fermes, langue),
               "", "_%s_" % t("attestation_sans_detail"), ""]
    return "\n".join(lignes)


def _compte_fermes(findings: list) -> int:
    """Nombre de découvertes fermées à la date de l'attestation."""
    fermes = 0
    for element in findings:
        statut = element.get("statut") if isinstance(element, dict) else element.statut
        valeur = statut.value if hasattr(statut, "value") else str(statut)
        if valeur == "ferme":
            fermes += 1
    return fermes


def _bloc_chiffres(compte: dict, fermes: int, langue: str) -> str:
    """Résultat agrégé : aucun détail technique, uniquement des compteurs."""
    lignes = [
        "- %s : %d" % (traduire("decouvertes", langue), sum(compte.values())),
        "- %s : %d" % (traduire("severite_critique", langue),
                       compte.get("critique", 0)),
        "- %s : %d" % (traduire("severite_eleve", langue), compte.get("eleve", 0)),
        "- %s : %d" % (traduire("ferme", langue), fermes),
    ]
    return "\n".join(lignes)


def trouvee(findings: list, identifiant: str) -> Optional[Finding]:
    """Retrouve une découverte par identifiant (liste d'enregistrements ou dicts)."""
    for element in findings or []:
        valeur = element.get("id") if isinstance(element, dict) else element.id
        if valeur == identifiant:
            return element if isinstance(element, Finding) else None
    return None
