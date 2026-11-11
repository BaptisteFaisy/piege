"""Piège — fournisseurs de modèle : protocole et fabrique.

Trois implémentations, une seule interface (CONTRACTS-INTERFACES §2) :
`local` (déterministe, hors ligne, par défaut en CI et pour `make demo`),
`inferhub` (HTTP compatible OpenAI, bibliothèque standard uniquement) et
`bedrock` (boto3 importé paresseusement). Le moteur ne connaît que le
protocole : changer de modèle ne change aucune autre ligne.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

__all__ = ["Fournisseur", "ReponseModele", "creer_fournisseur", "NOMS"]

NOMS = ("local", "inferhub", "bedrock")


@dataclass
class ReponseModele:
    """Réponse d'un modèle, avec les jetons consommés (mesure du coût)."""

    texte: str
    jetons_entree: int = 0
    jetons_sortie: int = 0
    modele: str = ""
    brut: dict = field(default_factory=dict)


class Fournisseur(Protocol):
    """Contrat gelé des fournisseurs de modèle."""

    nom: str

    def completer(self, messages: list[dict], graine: int,
                  max_jetons: int = 1500, temperature: float = 0.0) -> ReponseModele:
        """Complétion libre."""

    def sortie_structuree(self, messages: list[dict], schema: dict,
                          graine: int) -> dict:
        """Complétion dont la sortie doit valider `schema`."""


def creer_fournisseur(nom: Optional[str] = None, **options):
    """Fabrique de fournisseur ; `local` par défaut (aucun réseau)."""
    choix = (nom or "local").lower()
    if choix == "local":
        from piege.fournisseurs.local import FournisseurLocal

        return FournisseurLocal(**options)
    if choix == "inferhub":
        from piege.fournisseurs.inferhub import FournisseurInferhub

        return FournisseurInferhub(**options)
    if choix == "bedrock":
        from piege.fournisseurs.bedrock import FournisseurBedrock

        return FournisseurBedrock(**options)
    raise ValueError("fournisseur inconnu : %r (attendu %s)" % (nom, list(NOMS)))
