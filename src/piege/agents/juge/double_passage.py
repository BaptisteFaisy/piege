"""Piège — double passage du juge sur les réussites (spécification §18.3).

Un verdict `reussi` engage tout le rapport : il est donc rejoué par un second
passage indépendant, à **graine différente**. En cas de désaccord, la
découverte part en revue humaine au lieu d'être publiée. Le surcoût est
marginal (un verdict sur cinq environ) et c'est le seul endroit où se joue la
crédibilité du service.
"""

from __future__ import annotations

from piege.agents.juge import prompts
from piege.agents.juge.juge import juger
from piege.types import Technique, Verdict, VerdictValeur, hash_stable

__all__ = ["graine_secondaire", "second_passage", "confronter", "en_accord"]

MOTIF_DESACCORD = "desaccord_des_deux_passages"


def graine_secondaire(graine: int, technique_id: str) -> int:
    """Graine du second passage : différente, mais déterministe."""
    return (graine ^ hash_stable("second-passage:" + technique_id)) & 0xFFFFFFFF


def en_accord(premier: Verdict, second: Verdict) -> bool:
    """Deux verdicts concordent si la décision et l'impact sont identiques."""
    return (premier.verdict == second.verdict
            and premier.impact == second.impact
            and premier.garde_fou_declenche == second.garde_fou_declenche)


def confronter(premier: Verdict, second: Verdict) -> Verdict:
    """Fusionne les deux passages : accord → premier, désaccord → revue.

    En cas d'accord, la confiance retenue est la **plus basse** des deux :
    la prudence ne coûte rien et évite de publier un verdict surévalué.
    """
    if en_accord(premier, second):
        premier.confiance = min(premier.confiance, second.confiance)
        premier.modele = premier.modele or second.modele
        return premier
    return Verdict(
        verdict=VerdictValeur.AMBIGU, impact=None,
        citation=premier.citation or second.citation,
        confiance=min(premier.confiance, second.confiance),
        motif=MOTIF_DESACCORD,
        garde_fou_declenche=premier.garde_fou_declenche
        or second.garde_fou_declenche,
        graine=premier.graine, modele=premier.modele,
        revue_humaine=True, version_invite=prompts.VERSION_INVITE)


def second_passage(verdict: Verdict, technique: Technique, transcription: str,
                   fournisseur, modele: str = "") -> Verdict:
    """Rejuge une réussite ; les autres verdicts sont rendus tels quels."""
    if verdict.verdict is not VerdictValeur.REUSSI:
        return verdict
    autre = graine_secondaire(verdict.graine, technique.id)
    second = juger(technique, transcription, fournisseur, autre, modele=modele,
                   essai_max=1)
    return confronter(verdict, second)
