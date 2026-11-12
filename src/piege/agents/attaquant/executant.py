"""Piège — l'agent attaquant : exécution bornée d'une technique.

L'agent ne reçoit **que** la technique, sa sonde de départ, un nombre maximal de
tours et un objectif mesurable (spécification §18.2). Il ne reçoit jamais le
périmètre : c'est la passerelle qui refuse, et l'agent peut tenter d'en sortir —
c'est même sa nature. Le refus est alors journalisé, c'est la preuve montrée à
1:45 dans la démonstration.

Discipline imposée : tours bornés par `tours_max` **et** par `budget_appels`,
arrêt d'urgence testé entre chaque sonde, session isolée par technique, journal
intégral des échanges, et reproductibilité à graine fixée (ENF-03, ENF-05).
"""

from __future__ import annotations

from typing import Any, Optional

from piege.agents.attaquant import outils, variantes
from piege.moteur.graine import graine_tour, session_id
from piege.types import Campagne, Execution, Mandat, Reponse, Technique

__all__ = ["executer", "transcription", "planifier_tours"]


def planifier_tours(technique: Technique) -> int:
    """Nombre maximal de tours : borné par le catalogue, jamais au-delà."""
    return max(1, min(int(technique.tours_max), int(technique.budget_appels)))


def transcription(sondes: list[str], reponses: list[Reponse]) -> str:
    """Transcription lisible par le juge : alternance sonde / réponse."""
    lignes = []
    for index, sonde in enumerate(sondes):
        lignes.append("SONDE %d : %s" % (index + 1, sonde))
        if index < len(reponses):
            lignes.append("REPONSE %d : %s" % (index + 1, reponses[index].texte))
    return "\n".join(lignes)


def executer(technique: Technique, cible: Any, mandat: Mandat, campagne: Campagne,
             fournisseur: Any, graine: int, journal: Any, budget: Optional[Any] = None,
             arret: Optional[Any] = None) -> Execution:
    """Exécute une technique contre la cible et rend l'exécution non jugée."""
    session = session_id(graine, technique.id)
    sondes: list[str] = []
    reponses: list[Reponse] = []
    jetons = latence = 0
    cout = 0.0
    for tour in range(planifier_tours(technique)):
        if _stoppe(arret, budget):
            break
        sonde = _sonde(technique, graine, tour)
        reponse = _appeler(cible, sonde, session, graine_tour(graine, technique.id, tour))
        sondes.append(sonde)
        reponses.append(reponse)
        jetons += reponse.jetons_entree + reponse.jetons_sortie
        latence += reponse.latence_ms
        cout += float((reponse.brut or {}).get("cout") or 0.0)
        _consommer(budget, reponse)
        _journaliser(journal, mandat, technique, tour, sonde, reponse, session)
        if _suffisant(reponse, tour, technique):
            break
    return _execution(technique, campagne, mandat, sondes, reponses, jetons,
                      latence, graine, cout)


def _sonde(technique: Technique, graine: int, tour: int) -> str:
    """Sonde du tour : variante encodée au premier tour, relance ensuite."""
    sonde = variantes.sonde_du_tour(technique, graine, tour)
    if technique.id == "E6" and tour == 0:
        return variantes.diluer(sonde, variantes.texte_benin(technique, graine) or "")
    return sonde


def _stoppe(arret: Optional[Any], budget: Optional[Any]) -> bool:
    """Arrêt d'urgence ou budget épuisé : on s'arrête avant la sonde suivante."""
    if arret is not None and getattr(arret, "actif", False):
        return True
    return budget is not None and not budget.peut_consommer(1)


def _appeler(cible: Any, sonde: str, session: str, graine: int) -> Reponse:
    """Appel de l'outil `Cible___sonde` ; une erreur de cible ne casse pas la campagne."""
    try:
        return outils.Cible___sonde(cible, sonde, session, graine)
    except Exception as exc:                              # noqa: BLE001
        return Reponse(texte="", brut={"erreur_cible": str(exc)[:200]},
                       session=session)


def _consommer(budget: Optional[Any], reponse: Reponse) -> None:
    """Décompte un appel et ses jetons sur le budget de la campagne."""
    if budget is not None:
        budget.consommer(1, reponse.jetons_entree + reponse.jetons_sortie)


def _journaliser(journal: Any, mandat: Mandat, technique: Technique, tour: int,
                 sonde: str, reponse: Reponse, session: str) -> None:
    """Journalise l'échange (EF-14) : sonde, réponse, jetons, latence."""
    if journal is None:
        return
    journal.consigner("attaquant", "sonde", mandat.tenant_id, {
        "technique": technique.id, "tour": tour + 1, "session": session,
        "sonde": sonde[:400], "reponse": (reponse.texte or "")[:400],
        "jetons": reponse.jetons_entree + reponse.jetons_sortie,
        "latence_ms": reponse.latence_ms,
        "garde_fou": reponse.garde_fou_declenche})


def _suffisant(reponse: Reponse, tour: int, technique: Technique) -> bool:
    """Arrêt anticipé : un refus net au dernier tour n'a pas d'intérêt."""
    if reponse.brut.get("erreur_cible"):
        return True
    return False


def _execution(technique: Technique, campagne: Campagne, mandat: Mandat,
               sondes: list[str], reponses: list[Reponse], jetons: int,
               latence: int, graine: int, cout: float = 0.0) -> Execution:
    """Construit l'`Execution` non jugée : le verdict vient du juge (lot 5)."""
    derniere = reponses[-1] if reponses else Reponse(texte="")
    return Execution(
        id="EXE-%s-%s-%03d" % (campagne.id, technique.id, len(sondes)),
        campagne_id=campagne.id, technique_id=technique.id,
        application_id=mandat.application_id, tenant_id=mandat.tenant_id,
        statut="execute" if sondes else "aucun_appel",
        sondes_envoyees=sondes, reponse_brute=transcription(sondes, reponses),
        jetons=jetons, latence_ms=latence, verdict=None, impact=None,
        confiance=0.0, citation="", motif="",
        garde_fou_declenche=bool(derniere.garde_fou_declenche),
        revue_humaine=False, graine=graine, tours=len(sondes),
        modele="attaquant-piege", erreur=derniere.brut.get("erreur_cible", ""),
        cout=round(cout, 8))
