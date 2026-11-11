"""Piège — synthèse des faux refus : le chiffre qui vend le service (§13.3).

Le rapport affiche côte à côte ce qui fuit et ce qui est cassé. Ce module
prépare la colonne de droite : nombre de refus, répartition par criticité et
par cause, perte totale, heures de traitement manuel perdues, et les demandes
les plus coûteuses — celles qui déclenchent un correctif.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege import severite
from piege.types import CauseRefus, ClasseRefus, CorpusLegitime, FauxRefus

__all__ = ["resume", "par_criticite", "par_cause", "par_severite",
           "pertes_les_plus_fortes", "heures_perdues_totales"]


def par_criticite(refus: Iterable[FauxRefus]) -> dict[int, int]:
    """Nombre de faux refus par criticité métier déclarée."""
    compte: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for element in refus:
        compte[element.criticite_metier] = compte.get(element.criticite_metier, 0) + 1
    return compte


def par_cause(refus: Iterable[FauxRefus]) -> dict[str, int]:
    """Nombre de faux refus par cause identifiée (détermine le correctif)."""
    compte = {cause.value: 0 for cause in CauseRefus}
    for element in refus:
        cle = element.cause.value if isinstance(element.cause, CauseRefus) \
            else str(element.cause)
        compte[cle] = compte.get(cle, 0) + 1
    return compte


def par_severite(refus: Iterable[FauxRefus]) -> dict[str, int]:
    """Nombre de faux refus par sévérité (bloquant, majeur, mineur, nuisance)."""
    compte = {classe.value: 0 for classe in severite.SeveriteRefus}
    for element in refus:
        cle = element.severite.value if hasattr(element.severite, "value") \
            else str(element.severite)
        compte[cle] = compte.get(cle, 0) + 1
    return compte


def heures_perdues_totales(refus: Iterable[FauxRefus]) -> float:
    """Heures de traitement manuel perdues par mois, toutes demandes confondues."""
    total = 0.0
    for element in refus:
        total += severite.heures_perdues(element.frequence_mensuelle,
                                         element.minutes_manuelles)
    return round(total, 2)


def pertes_les_plus_fortes(refus: Iterable[FauxRefus], limite: int = 5) -> list[dict]:
    """Les demandes les plus coûteuses, triées par perte puis criticité."""
    tries = sorted(refus, key=lambda r: (-r.perte, -r.criticite_metier, r.id))
    return [{"demande_id": r.demande_id, "perte": r.perte,
             "criticite": r.criticite_metier,
             "frequence_mensuelle": r.frequence_mensuelle,
             "severite": getattr(r.severite, "value", str(r.severite)),
             "cause": getattr(r.cause, "value", str(r.cause))}
            for r in tries[:max(0, limite)]]


def resume(refus: list[FauxRefus], corpus: Optional[CorpusLegitime] = None,
           campagne_id: str = "") -> dict:
    """Synthèse complète de la famille G, prête pour le rapport et le portail."""
    from piege.familles.faux_refus.executant import taux_de_refus

    total_demandes = len(corpus.demandes) if corpus and corpus.demandes else 0
    perte_totale = sum(element.perte for element in refus)
    classes: dict[str, int] = {classe.value: 0 for classe in ClasseRefus}
    for element in refus:
        cle = element.classe.value if isinstance(element.classe, ClasseRefus) \
            else str(element.classe)
        classes[cle] = classes.get(cle, 0) + 1
    return {
        "campagne_id": campagne_id,
        "corpus_id": corpus.id if corpus else "",
        "demandes_testees": total_demandes,
        "faux_refus": len(refus),
        "taux_de_refus": taux_de_refus(corpus, refus),
        "perte_totale": perte_totale,
        "heures_perdues_par_mois": heures_perdues_totales(refus),
        "par_criticite": par_criticite(refus),
        "par_cause": par_cause(refus),
        "par_severite": par_severite(refus),
        "par_classe": classes,
        "top_pertes": pertes_les_plus_fortes(refus),
        "corpus_disponible": bool(total_demandes),
    }
