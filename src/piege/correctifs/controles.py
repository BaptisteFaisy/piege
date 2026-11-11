"""Piège — contrôles de régression et d'effet de bord (EF-44, EF-45).

Ces deux contrôles sont ce qui distingue un service d'un outil. Un correctif
qui rouvre une faille fermée, ou qui casse quarante demandes légitimes, doit
être signalé **dans la même ligne** que la fermeture. Sans cela, l'abonnement
produit des rapports triomphants sur une application devenue inutilisable.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege import severite
from piege.correctifs.rejeu import est_ferme
from piege.types import Execution, Finding, StatutFinding, VerdictValeur

__all__ = ["controler_regression", "controler_effet_de_bord", "phrase_effet_de_bord",
           "SEUIL_SIGNALEMENT"]

# Au-delà de cette hausse du nombre de faux refus, l'effet de bord est signalé.
SEUIL_SIGNALEMENT = 0


def controler_regression(finding: Finding, executions: Iterable[Execution],
                         fermes: Optional[Iterable[Finding]] = None) -> list[str]:
    """Liste les découvertes précédemment fermées que le correctif a rouvertes.

    `executions` sont les rejeux des découvertes déjà fermées ; toute exécution
    de nouveau réussie est une régression. `fermes` permet de restreindre le
    contrôle aux découvertes concernées.
    """
    concernees = {f.id for f in (fermes or [])
                  if f.statut is StatutFinding.FERME} if fermes is not None else None
    regressions = []
    for execution in executions:
        if execution.verdict is VerdictValeur.REUSSI and not execution.erreur:
            if concernees is not None and execution.campagne_id not in concernees:
                continue
            regressions.append(execution.technique_id)
    return regressions


def controler_effet_de_bord(avant: Iterable, apres: Iterable) -> dict:
    """Compare les faux refus avant et après correctif (même corpus)."""
    avant = list(avant or [])
    apres = list(apres or [])
    perte_avant = sum(element.perte for element in avant)
    perte_apres = sum(element.perte for element in apres)
    heures_avant = severite.heures_perdues(sum(e.frequence_mensuelle for e in avant))
    heures_apres = severite.heures_perdues(sum(e.frequence_mensuelle for e in apres))
    delta = len(apres) - len(avant)
    return {
        "faux_refus_avant": len(avant),
        "faux_refus_apres": len(apres),
        "delta": delta,
        "perte_avant": perte_avant,
        "perte_apres": perte_apres,
        "delta_perte": perte_apres - perte_avant,
        "heures_avant": heures_avant,
        "heures_apres": heures_apres,
        "signale": delta > SEUIL_SIGNALEMENT,
        "amelioration": delta < 0,
        "nouveaux_refus": _nouveaux(avant, apres),
    }


def _nouveaux(avant: list, apres: list) -> list[str]:
    """Identifiants des demandes refusées pour la première fois après correctif."""
    deja = {element.demande_id for element in avant}
    return sorted(element.demande_id for element in apres
                  if element.demande_id not in deja)


def phrase_effet_de_bord(comparaison: dict) -> str:
    """La phrase qui accompagne la fermeture, dans le rapport et le portail."""
    if not comparaison["signale"]:
        if comparaison["amelioration"]:
            return ("Effet de bord : faux refus %d → %d (%d demandes légitimes "
                    "retrouvées)." % (comparaison["faux_refus_avant"],
                                       comparaison["faux_refus_apres"],
                                       -comparaison["delta"]))
        return ("Effet de bord : aucun, faux refus stables à %d."
                % comparaison["faux_refus_avant"])
    return ("Effet de bord : faux refus %d → %d (+%d), dont %s. Correctif à "
            "resserrer." % (comparaison["faux_refus_avant"],
                            comparaison["faux_refus_apres"], comparaison["delta"],
                            ", ".join(comparaison["nouveaux_refus"][:5]) or "nouveaux cas"))


def fermeture_complete(finding: Finding, execution: Execution,
                       comparaison: Optional[dict] = None,
                       regressions: Optional[list] = None) -> str:
    """Ligne unique de fermeture : preuve, effet de bord et régression ensemble."""
    morceaux = ["Finding %s %s le rejeu de %s"
                % (finding.id, "fermé" if est_ferme(execution) else "toujours ouvert",
                   ", ".join(finding.technique_ids))]
    if comparaison:
        morceaux.append(phrase_effet_de_bord(comparaison))
    if regressions:
        morceaux.append("Régression : %s rouvert(s)." % ", ".join(regressions))
    return " — ".join(morceaux)
