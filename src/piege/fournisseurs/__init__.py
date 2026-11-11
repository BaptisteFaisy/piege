"""Piège — fournisseurs de modèle (local, InferHub, Bedrock)."""

from piege.fournisseurs.base import (NOMS, Fournisseur, ReponseModele,
                                     creer_fournisseur)

__all__ = ["Fournisseur", "ReponseModele", "creer_fournisseur", "NOMS"]
