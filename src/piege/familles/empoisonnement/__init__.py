"""Piège — famille F : empoisonnement du corpus RAG.

Le différenciateur du produit : déposer un document dans une source indexée et
vérifier si l'assistant le relaie. C'est l'attaque la plus réaliste du marché —
elle ne demande aucun accès technique, seulement le droit de déposer un fichier.

Point d'entrée : `executer(technique, cible, mandat, index_test, graine,
journal)`. L'index de test se manipule avec le contexte `index_isole`, qui
garantit la destruction même en cas d'erreur (EF-17).
"""

from piege.familles.empoisonnement.executant import MESURES_DISPONIBLES, executer
from piege.familles.empoisonnement.gabarits import (MARQUEUR_DEPOT,
                                                    charger_gabarit,
                                                    chemin_gabarit,
                                                    document_depose, est_marque,
                                                    marquer)
from piege.familles.empoisonnement.index_test import (creer_index_test, detruire,
                                                      index_isole)
from piege.familles.empoisonnement.mesures import (Mesure, mesurer_execution,
                                                   mesurer_persistance,
                                                   mesurer_relais)

__all__ = [
    "executer", "MESURES_DISPONIBLES", "creer_index_test", "detruire",
    "index_isole", "Mesure", "mesurer_relais", "mesurer_execution",
    "mesurer_persistance", "charger_gabarit", "chemin_gabarit",
    "document_depose", "marquer", "est_marque", "MARQUEUR_DEPOT",
]
