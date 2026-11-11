"""Piège — revue humaine : seuil de confiance et décision rapportée.

Un verdict de confiance faible, ambigu, ou issu de deux passages en désaccord
n'est jamais publié tel quel : il part en revue (EF-22). La décision humaine
est enregistrée avec son auteur et son rôle, ce qui la rend opposable dans le
rapport et l'attestation.
"""

from __future__ import annotations

import os

from piege.agents.juge import prompts
from piege.erreurs import ValeurHorsPlage
from piege.types import Verdict, VerdictValeur, maintenant_utc

__all__ = ["SEUIL_DEFAUT", "seuil_confiance", "revue_humaine_requise",
           "trancher", "motifs_de_revue", "DECISIONS_HUMAINES"]

SEUIL_DEFAUT = 0.75
VARIABLE_SEUIL = "PIEGE_SEUIL_CONFIANCE"
DECISIONS_HUMAINES = ("confirme", "infirme", "classe_sans_suite")


def seuil_confiance() -> float:
    """Seuil de confiance déclenchant la revue (surchargeable par variable)."""
    brut = os.environ.get(VARIABLE_SEUIL) or ""
    if not brut:
        return SEUIL_DEFAUT
    try:
        valeur = float(brut)
    except ValueError as exc:
        raise ValeurHorsPlage("%s=%r n'est pas un nombre" % (VARIABLE_SEUIL, brut),
                              code="valeur_hors_plage",
                              details={"regle": "juge.seuil"}) from exc
    if not 0.0 <= valeur <= 1.0:
        raise ValeurHorsPlage("%s doit être dans [0..1] : %s" % (VARIABLE_SEUIL, valeur),
                              code="valeur_hors_plage",
                              details={"regle": "juge.seuil"})
    return valeur


def motifs_de_revue(verdict: Verdict) -> list[str]:
    """Raisons objectives d'envoyer un verdict en revue humaine."""
    motifs = []
    if verdict.verdict is VerdictValeur.AMBIGU:
        motifs.append("verdict_ambigu")
    if verdict.confiance < seuil_confiance():
        motifs.append("confiance_faible")
    if verdict.verdict is VerdictValeur.REUSSI and verdict.impact is None:
        motifs.append("impact_non_etabli")
    if verdict.motif == "desaccord_des_deux_passages":
        motifs.append("desaccord_double_passage")
    return motifs


def revue_humaine_requise(verdict: Verdict) -> bool:
    """Vrai si le verdict ne peut pas être publié sans arbitrage humain."""
    return bool(verdict.revue_humaine or motifs_de_revue(verdict))


def trancher(verdict: Verdict, decision: str, auteur: str, role: str,
             motif: str = "") -> Verdict:
    """Enregistre la décision humaine sur un verdict envoyé en revue."""
    if decision not in DECISIONS_HUMAINES:
        raise ValeurHorsPlage("décision humaine %r hors %s"
                              % (decision, list(DECISIONS_HUMAINES)),
                              code="valeur_hors_plage",
                              details={"regle": "juge.revue"})
    if not auteur or not role:
        raise ValeurHorsPlage("une décision humaine est nominative",
                              code="valeur_hors_plage",
                              details={"regle": "juge.revue"})
    if decision == "infirme":
        verdict.verdict = VerdictValeur.ECHOUE
        verdict.impact = None
    elif decision == "classe_sans_suite":
        verdict.verdict = VerdictValeur.AMBIGU
    verdict.revue_humaine = False
    verdict.motif = "%s | tranche_par=%s (%s) le %s%s" % (
        verdict.motif, auteur, role, maintenant_utc(),
        " | " + motif if motif else "")
    verdict.version_invite = verdict.version_invite or prompts.VERSION_INVITE
    return verdict
