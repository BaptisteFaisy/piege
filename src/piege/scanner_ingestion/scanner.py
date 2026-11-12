"""Piège — scanner d'ingestion RAG : détecter un document piégé AVANT l'index.

Produit de défense autonome (le pendant défensif de la famille F) : il analyse
un document candidat à l'indexation et rend un verdict actionnable — sain,
suspect ou malveillant — avec les motifs trouvés, leur sévérité, une citation et
la recommandation de correctif. Pensé pour être branché sur un pipeline
d'ingestion (Knowledge Bases, dépôt RH, wiki) et pour être vendable seul.

Aucun réseau, aucune dépendance tierce, déterministe : le même document donne
toujours le même rapport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from piege.scanner_ingestion.motifs import (MARQUEURS_CONTRÔLE, MOTIFS, Motif)
from piege.types import empreinte

__all__ = ["Alerte", "Rapport", "scanner_document", "scanner_corpus",
           "NIVEAUX", "decision"]

NIVEAUX = ("sain", "suspect", "malveillant")
_POIDS = {"faible": 1, "moyenne": 3, "haute": 7}
_SEUIL_SUSPECT = 3
_SEUIL_MALVEILLANT = 7


@dataclass
class Alerte:
    """Un motif détecté : nom, sévérité, citation, recommandation."""

    motif: str
    severite: str
    famille: str
    citation: str
    recommandation: str

    def vers_dict(self) -> dict:
        """Version sérialisable."""
        return {"motif": self.motif, "severite": self.severite,
                "famille": self.famille, "citation": self.citation,
                "recommandation": self.recommandation}


@dataclass
class Rapport:
    """Verdict de scan d'un document."""

    nom: str
    niveau: str
    score: int
    alertes: list = field(default_factory=list)
    empreinte: str = ""
    octets: int = 0

    def vers_dict(self) -> dict:
        """Version sérialisable, pour l'API et le rapport."""
        return {"nom": self.nom, "niveau": self.niveau, "score": self.score,
                "empreinte": self.empreinte, "octets": self.octets,
                "alertes": [a.vers_dict() for a in self.alertes],
                "decision": decision(self.niveau)}

    @property
    def bloquant(self) -> bool:
        """Vrai si le document ne doit pas être indexé en l'état."""
        return self.niveau == "malveillant"


def decision(niveau: str) -> str:
    """Action recommandée selon le niveau de risque."""
    if niveau == "malveillant":
        return "rejeter"
    if niveau == "suspect":
        return "revue_humaine"
    return "indexer"


def _citation(texte: str, position: int, longueur: int = 120) -> str:
    """Extrait borné autour de la position trouvée."""
    debut = max(0, position - 20)
    return texte[debut:debut + longueur].replace("\n", " ").strip()


def _scanner_motifs(texte: str) -> list[Alerte]:
    """Applique chaque motif regex au texte."""
    alertes = []
    for motif in MOTIFS:
        trouve = motif.regex.search(texte)
        if trouve:
            alertes.append(Alerte(motif.nom, motif.severite, motif.famille,
                                  _citation(texte, trouve.start()),
                                  motif.recommandation))
    return alertes


def _scanner_contrôles(texte: str) -> list[Alerte]:
    """Détecte les caractères de contrôle invisibles (technique B10)."""
    alertes = []
    for caractere, nom in MARQUEURS_CONTRÔLE.items():
        if caractere in texte:
            alertes.append(Alerte("caractere_controle:%s" % nom, "moyenne",
                                  "controle",
                                  "caractère invisible U+%04X présent" % ord(caractere),
                                  "Normaliser Unicode et retirer les caractères "
                                  "invisibles à l'ingestion."))
    return alertes


def _niveau(score: int, alertes: Iterable[Alerte]) -> str:
    """Niveau de risque : toute alerte haute est malveillante, sinon seuils."""
    alertes = list(alertes)
    if any(a.severite == "haute" for a in alertes):
        return "malveillant"
    if score >= _SEUIL_MALVEILLANT:
        return "malveillant"
    if score >= _SEUIL_SUSPECT:
        return "suspect"
    return "sain"


def scanner_document(contenu: str, nom: str = "") -> Rapport:
    """Scanne un document candidat à l'indexation et rend son verdict."""
    texte = contenu or ""
    alertes = _scanner_motifs(texte) + _scanner_contrôles(texte)
    score = sum(_POIDS.get(a.severite, 1) for a in alertes)
    niveau = _niveau(score, alertes)
    return Rapport(nom=nom or "document", niveau=niveau, score=score,
                   alertes=alertes, empreinte=empreinte(texte),
                   octets=len(texte.encode("utf-8")))


def scanner_corpus(documents: dict, seuil: str = "suspect") -> dict:
    """Scanne un lot de documents ; rend ceux au-delà du seuil.

    `documents` est un dictionnaire nom → contenu. Utile pour auditer un corpus
    existant avant réindexation (technique F6, persistance).
    """
    ordre = {"sain": 0, "suspect": 1, "malveillant": 2}
    rapport = {}
    a_signaler = []
    for nom, contenu in (documents or {}).items():
        resultat = scanner_document(contenu, nom)
        rapport[nom] = resultat
        if ordre[resultat.niveau] >= ordre[seuil]:
            a_signaler.append(nom)
    return {"rapports": rapport, "a_signaler": sorted(a_signaler),
            "total": len(rapport), "sains": len(rapport) - len(a_signaler)}
