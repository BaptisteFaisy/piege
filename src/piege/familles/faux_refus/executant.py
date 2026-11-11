"""Piège — exécution de la famille G : mesurer ce qui est cassé (EF-31..EF-34).

Chaque demande légitime du corpus client est soumise à l'application **en
session vierge**, classée, puis chiffrée : fréquence mensuelle × criticité
métier donne la perte, et la perte donne la sévérité (spécification §12.3).

Sans corpus, la famille refuse de tourner et le dit explicitement : un chiffre
vide dans un rapport client vaut mieux qu'un zéro inventé.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.erreurs import CorpusLegitimeAbsent
from piege.familles.faux_refus import classifieur
from piege.moteur.graine import graine_etiquetee, session_id
from piege.types import (CorpusLegitime, DemandeLegitime, FauxRefus, Reponse,
                         maintenant_utc)
from piege import severite

__all__ = ["executer", "executer_demande", "refuser_sans_corpus",
           "taux_de_refus"]


def refuser_sans_corpus(corpus: Optional[CorpusLegitime]) -> None:
    """Refus explicite quand le corpus manque (EF-34) : jamais de chiffre vide."""
    if corpus is None or not corpus.demandes:
        raise CorpusLegitimeAbsent(
            "famille G non exécutable : aucun corpus de demandes légitimes "
            "fourni par le client. Le rapport indiquera cette absence au lieu "
            "de publier un taux de faux refus.",
            code="corpus_legitime_absent",
            details={"regle": "famille_g.corpus"})


def executer(corpus: CorpusLegitime, cible: Any, graine: int, journal: Any,
             campagne_id: str = "", sequence: int = 1) -> list[FauxRefus]:
    """Exécute tout le corpus et rend les faux refus mesurés.

    Seules les demandes réellement refusées (refus, refus partiel, hors sujet)
    produisent un enregistrement : le rapport distingue « ce qui fuit » de
    « ce qui est cassé » sans noyer les réponses correctes.
    """
    refuser_sans_corpus(corpus)
    refus: list[FauxRefus] = []
    for index, demande in enumerate(corpus.demandes, start=sequence):
        mesure = executer_demande(demande, cible, graine, campagne_id, index)
        if mesure is not None:
            refus.append(mesure)
    _journaliser(journal, corpus, campagne_id, len(corpus.demandes), len(refus))
    return refus


def executer_demande(demande: DemandeLegitime, cible: Any, graine: int,
                     campagne_id: str = "", index: int = 1) -> Optional[FauxRefus]:
    """Soumet une demande en session vierge et la classe (EF-31, EF-32)."""
    session = session_id(graine_etiquetee(graine, "famille-g"), demande.id)
    reponse = cible.sonder(demande.texte, session, graine)
    classe = classifieur.classifier(reponse)
    if classifieur.est_justifie(reponse, demande.attendu):
        return None
    if classe.value == "reponse_complete" or classe.value == "reponse_partielle":
        return None
    return _enregistrement(demande, reponse, classe, campagne_id, index)


def _enregistrement(demande: DemandeLegitime, reponse: Reponse, classe,
                    campagne_id: str, index: int) -> FauxRefus:
    """Construit l'enregistrement de faux refus, perte et sévérité comprises."""
    perte = severite.perte(demande.frequence_mensuelle, demande.criticite)
    return FauxRefus(
        id="REF-%s-%04d" % (campagne_id or "locale", index),
        campagne_id=campagne_id, application_id="", tenant_id="",
        demande_id=demande.id, reponse_ref=(reponse.texte or "")[:400],
        classe=classe, cause=classifieur.cause(reponse),
        frequence_mensuelle=demande.frequence_mensuelle,
        criticite_metier=demande.criticite, perte=perte,
        severite=severite.severite_faux_refus(demande.frequence_mensuelle,
                                              demande.criticite))


def taux_de_refus(corpus: CorpusLegitime, refus: list[FauxRefus]) -> float:
    """Taux de refus sur le corpus, entre 0 et 1 (KPI-5)."""
    total = len(corpus.demandes) if corpus and corpus.demandes else 0
    if not total:
        return 0.0
    return round(len(refus) / total, 4)


def _journaliser(journal: Any, corpus: CorpusLegitime, campagne_id: str,
                 total: int, refus: int) -> None:
    """Journalise la fin de la famille G (aucun contenu de demande)."""
    if journal is None:
        return
    journal.consigner("famille_g", "corpus_execute", corpus.tenant_id,
                      {"campagne": campagne_id, "corpus": corpus.id,
                       "demandes": total, "faux_refus": refus,
                       "date": maintenant_utc()})
