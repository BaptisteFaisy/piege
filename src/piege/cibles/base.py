"""Piège — contrat des cibles : le moteur ne parle jamais HTTP lui-même.

Une *cible* est l'application d'IA du client. Le moteur lui pose des questions
et reçoit des `Reponse` ; il ne connaît ni son protocole, ni son modèle, ni son
corpus. Trois implémentations : locale (déterministe, hors ligne), HTTP et
Bedrock.
"""

from __future__ import annotations

from typing import Any, Protocol

from piege.types import Reponse

__all__ = ["Cible", "creer_cible", "TYPES_CIBLE"]

TYPES_CIBLE = ("local", "http", "bedrock", "inferhub")


class Cible(Protocol):
    """Protocole d'une cible (CONTRACTS-INTERFACES §1)."""

    id: str
    application_id: str

    def sonder(self, demande: str, session: str, graine: int) -> Reponse:
        """Envoie une sonde et rend la réponse de l'application."""

    def deposer_document(self, chemin: str, contenu: str, session: str) -> str:
        """Dépose un document (famille F) et rend son identifiant."""

    def mesurer(self, requete: str, session: str) -> Reponse:
        """Mesure l'effet d'un dépôt, sans compter comme une attaque."""

    def reindexer(self, session: str) -> None:
        """Réindexe l'index de test de la campagne."""

    def detruire_index(self, index_id: str) -> None:
        """Détruit l'index de test (EF-17) : rien ne survit."""

    def journaliser(self, evenement: dict) -> None:
        """Journalise un événement côté cible."""


def creer_cible(spec: dict) -> Any:
    """Construit la cible décrite par une spécification."""
    spec = dict(spec or {})
    kind = str(spec.get("type", "local")).lower()
    if kind == "local":
        from piege.cibles.locale import CibleLocaleDemo

        return CibleLocaleDemo(spec)
    if kind == "http":
        from piege.cibles.http import CibleHttp

        return CibleHttp(spec)
    if kind == "bedrock":
        from piege.cibles.bedrock import CibleBedrock

        return CibleBedrock(spec)
    if kind == "inferhub":
        from piege.cibles.inferhub import CibleInferhub

        return CibleInferhub(spec)
    raise ValueError("type de cible inconnu : %r (attendu %s)"
                     % (kind, list(TYPES_CIBLE)))
