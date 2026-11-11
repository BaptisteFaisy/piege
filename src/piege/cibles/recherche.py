"""Piège — recherche documentaire déterministe de la cible de démonstration.

Une récupération de type RAG, sans embedding ni réseau : score TF-IDF sur des
jetons normalisés, égalités départagées par le nom du document. Déterministe à
corpus fixé, ce qui rend les campagnes reproductibles (ENF-05).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

__all__ = ["Document", "Index", "normaliser", "jetons", "construire_index",
           "rechercher"]

_MOT = re.compile(r"[a-z0-9]+")
_MOTS_VIDES = {"le", "la", "les", "un", "une", "des", "du", "de", "et", "est",
               "en", "dans", "pour", "par", "sur", "au", "aux", "ce", "cette",
               "ces", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa",
               "ses", "que", "qui", "quoi", "comment", "quelle", "quel",
               "quels", "quelles", "je", "tu", "vous", "nous", "il", "elle",
               "a", "à", "the", "of", "and", "to", "is", "in", "for"}


@dataclass
class Document:
    """Un document du corpus : nom, titre, contenu et marqueurs."""

    nom: str
    titre: str
    contenu: str
    sensible: bool = False
    officiel: bool = False
    depose: bool = False
    jetons: dict = field(default_factory=dict)


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation : base de la comparaison."""
    sans_accents = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return sans_accents.lower()


def jetons(texte: str) -> list[str]:
    """Jetons significatifs d'un texte (mots vides retirés)."""
    return [mot for mot in _MOT.findall(normaliser(texte))
            if mot not in _MOTS_VIDES and len(mot) > 1]


@dataclass
class Index:
    """Index de recherche : documents, fréquences et poids inverses."""

    documents: list[Document] = field(default_factory=list)
    frequencies: dict = field(default_factory=dict)
    poids: dict = field(default_factory=dict)


def _compter(document: Document) -> dict:
    """Compte les occurrences de chaque jeton d'un document."""
    compte: dict[str, int] = {}
    for jeton in jetons(document.titre + " " + document.contenu):
        compte[jeton] = compte.get(jeton, 0) + 1
    document.jetons = compte
    return compte


def construire_index(documents: list[Document]) -> Index:
    """Construit l'index d'un corpus (documents déjà chargés)."""
    index = Index(documents=list(documents))
    documents_contenant: dict[str, int] = {}
    for document in index.documents:
        for jeton in _compter(document):
            documents_contenant[jeton] = documents_contenant.get(jeton, 0) + 1
    total = max(1, len(index.documents))
    index.frequencies = documents_contenant
    index.poids = {jeton: math.log(1.0 + total / nombre)
                   for jeton, nombre in documents_contenant.items()}
    return index


def _score(requete_jetons: list[str], document: Document, index: Index) -> float:
    """Score d'un document pour une requête : somme des poids des jetons présents."""
    score = 0.0
    for jeton in set(requete_jetons):
        occurrences = document.jetons.get(jeton, 0)
        if not occurrences:
            continue
        score += index.poids.get(jeton, 1.0) * (1.0 + math.log(occurrences))
    if document.depose:
        score += 0.5          # un document déposé est récent, donc favorisé
    return score


def rechercher(requete: str, index: Index, k: int = 3) -> list[Document]:
    """Les k documents les plus pertinents, ordre stable et déterministe."""
    requete_jetons = jetons(requete)
    if not requete_jetons:
        return []
    scores = [(_score(requete_jetons, document, index), document.nom, document)
              for document in index.documents]
    scores = [s for s in scores if s[0] > 0.0]
    scores.sort(key=lambda s: (-s[0], s[1]))
    return [document for _, _, document in scores[:max(0, k)]]
