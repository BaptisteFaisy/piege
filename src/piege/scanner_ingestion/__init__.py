"""Piège — scanner d'ingestion RAG (défense, pendant de la famille F).

Point d'entrée : `scanner_document(contenu, nom)` rend un verdict sain / suspect
/ malveillant avec les motifs, citations et recommandations. `scanner_corpus`
audite un lot entier avant réindexation.
"""

from piege.scanner_ingestion.motifs import MARQUEURS_CONTRÔLE, MOTIFS, Motif
from piege.scanner_ingestion.scanner import (NIVEAUX, Alerte, Rapport, decision,
                                             scanner_corpus, scanner_document)

__all__ = ["scanner_document", "scanner_corpus", "Alerte", "Rapport", "decision",
           "NIVEAUX", "MOTIFS", "Motif", "MARQUEURS_CONTRÔLE"]
