"""Piège — les trois outils de l'agent attaquant (spécification §18.1).

Les noms sont **exacts** : c'est sur eux que la politique de périmètre statue
(`Cible___sonde`, `Cible___deposit`, `Cible___mesure`). Chaque outil est une
couche mince au-dessus du protocole `Cible`, sans logique métier : la décision
d'autoriser appartient à la passerelle, jamais à l'agent.
"""

from __future__ import annotations

from typing import Any

from piege.types import Reponse

__all__ = ["Cible___sonde", "Cible___deposit", "Cible___mesure", "OUTILS"]

OUTILS = ("Cible___sonde", "Cible___deposit", "Cible___mesure")


def Cible___sonde(cible: Any, demande: str, session: str, graine: int) -> Reponse:
    """Envoie une sonde à la cible (outil principal de l'attaquant)."""
    return cible.sonder(demande, session, graine)


def Cible___deposit(cible: Any, chemin: str, contenu: str, session: str) -> str:
    """Dépose un document dans l'index de test de la campagne (famille F)."""
    return cible.deposer_document(chemin, contenu, session)


def Cible___mesure(cible: Any, requete: str, session: str) -> Reponse:
    """Mesure un effet sans compter comme une attaque supplémentaire."""
    return cible.mesurer(requete, session)
