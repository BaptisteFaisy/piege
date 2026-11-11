"""Piège — exécution d'une technique de la famille F (empoisonnement).

Séquence imposée par la spécification §14.2 : mesure de référence, dépôt du
document piégé dans l'**index de test**, réindexation, mesure, puis mesure de
persistance et destruction. Rien ne touche le corpus du client.

Chaque étape est journalisée : c'est ce journal qui prouve, à l'audit, que le
dépôt était un test autorisé et non une modification réelle du corpus.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.familles.empoisonnement import gabarits
from piege.familles.empoisonnement.mesures import (Mesure, mesurer_execution,
                                                   mesurer_persistance,
                                                   mesurer_relais)
from piege.moteur.graine import session_id
from piege.types import Mandat, Technique

__all__ = ["executer", "MESURES_DISPONIBLES"]

MESURES_DISPONIBLES = ("relais", "execution", "persistance")


def executer(technique: Technique, cible: Any, mandat: Mandat, index_test: str,
             graine: int, journal: Any, dossier_catalogue: str = "catalogue",
             campagne_id: str = "", contenu: Optional[str] = None) -> list[Mesure]:
    """Exécute une technique F et rend ses mesures (relais, exécution, persistance).

    `index_test` est à la fois l'index de test de la campagne et la clé de
    session utilisée par la cible : dépôt, mesure et destruction portent
    exactement la même clé, ce qui garantit qu'aucune trace ne survit.
    """
    session = index_test or session_id(graine, technique.id)
    sonde = technique.sonde_initiale
    _journaliser(journal, mandat, "mesure_avant", technique, index_test, session)
    avant = cible.mesurer(sonde, session)
    chemin, document = gabarits.document_depose(technique, campagne_id or mandat.id,
                                                dossier_catalogue, contenu=contenu)
    cible.deposer_document(chemin, document, session)
    _journaliser(journal, mandat, "depot_document", technique, index_test, session,
                 {"document": chemin, "octets": len(document)})
    cible.reindexer(session)
    apres = cible.mesurer(sonde, session)
    _journaliser(journal, mandat, "mesure_apres", technique, index_test, session)
    mesures = [mesurer_relais(avant, apres, document),
               mesurer_execution(avant, apres)]
    if "persistance" in technique.mesures:
        mesures.append(_persistance(cible, sonde, session, avant, index_test,
                                    journal, mandat, technique))
    return _filtrer(mesures, technique)


def _persistance(cible: Any, sonde: str, session: str, avant: Any,
                 index_test: str, journal: Any, mandat: Mandat,
                 technique: Technique) -> Mesure:
    """Mesure F6 : survie à la réindexation, nettoyage à la destruction."""
    cible.reindexer(session)
    apres_reindexation = cible.mesurer(sonde, session)
    _journaliser(journal, mandat, "mesure_reindexation", technique, index_test,
                 session)
    cible.detruire_index(index_test)
    apres_destruction = cible.mesurer(sonde, session)
    _journaliser(journal, mandat, "mesure_apres_destruction", technique,
                 index_test, session)
    return mesurer_persistance(apres_reindexation, apres_destruction, avant)


def _filtrer(mesures: list[Mesure], technique: Technique) -> list[Mesure]:
    """Ne conserve que les mesures déclarées par la technique, dans son ordre."""
    demandees = [m for m in technique.mesures if m in MESURES_DISPONIBLES]
    if not demandees:
        return mesures
    par_nom = {mesure.nom: mesure for mesure in mesures}
    return [par_nom[nom] for nom in demandees if nom in par_nom]


def _journaliser(journal: Any, mandat: Mandat, quoi: str, technique: Technique,
                 index_test: str, session: str, details: Optional[dict] = None) -> None:
    """Journalise une étape de la famille F (aucun contenu de document)."""
    if journal is None:
        return
    complement = {"technique": technique.id, "index": index_test,
                  "session": session, "famille": "F"}
    complement.update(details or {})
    journal.consigner("famille_f", quoi, mandat.tenant_id, complement)
