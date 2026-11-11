"""Piège — compteurs d'exécution : appels, jetons, coût.

Un compteur par campagne, alimenté par le moteur à chaque échange. Il est
**thread-safe** : une campagne s'exécute en parallélisme borné, et le coût
mesuré doit rester exact quel que soit l'ordre d'arrivée des techniques
(ENF-10, KPI-7).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

__all__ = ["Compteur", "compteurs_par_modele"]


@dataclass
class Compteur:
    """Compteurs cumulés d'une campagne (forme gelée par le contrat)."""

    appels: int = 0
    jetons_entree: int = 0
    jetons_sortie: int = 0
    cout: float = 0.0
    par_modele: dict = field(default_factory=dict)
    # Verrou réentrant : `fusionner` appelle `ajouter` en tenant le verrou.
    _verrou: threading.RLock = field(default_factory=threading.RLock, repr=False,
                                     compare=False)

    def ajouter(self, appels: int = 0, jetons_entree: int = 0,
                jetons_sortie: int = 0, cout: float = 0.0,
                modele: str = "") -> None:
        """Ajoute une consommation ; l'agrégation par modèle est automatique."""
        with self._verrou:
            self.appels += appels
            self.jetons_entree += jetons_entree
            self.jetons_sortie += jetons_sortie
            self.cout = round(self.cout + cout, 6)
            if modele:
                part = self.par_modele.setdefault(
                    modele, {"appels": 0, "jetons_entree": 0, "jetons_sortie": 0,
                             "cout": 0.0})
                part["appels"] += appels
                part["jetons_entree"] += jetons_entree
                part["jetons_sortie"] += jetons_sortie
                part["cout"] = round(part["cout"] + cout, 6)

    def fusionner(self, autre: "Compteur") -> "Compteur":
        """Fusionne un autre compteur : totaux et répartition, sans double compte."""
        with self._verrou:
            with autre._verrou:
                self.appels += autre.appels
                self.jetons_entree += autre.jetons_entree
                self.jetons_sortie += autre.jetons_sortie
                self.cout = round(self.cout + autre.cout, 6)
                for modele, part in autre.par_modele.items():
                    self._ajouter_part(modele, part)
        return self

    def _ajouter_part(self, modele: str, part: dict) -> None:
        """Ajoute une part par modèle à la répartition (verrou déjà tenu)."""
        cible = self.par_modele.setdefault(
            modele, {"appels": 0, "jetons_entree": 0, "jetons_sortie": 0,
                     "cout": 0.0})
        cible["appels"] += int(part.get("appels", 0))
        cible["jetons_entree"] += int(part.get("jetons_entree", 0))
        cible["jetons_sortie"] += int(part.get("jetons_sortie", 0))
        cible["cout"] = round(cible["cout"] + float(part.get("cout", 0.0)), 6)

    @property
    def jetons(self) -> int:
        """Total des jetons, entrée et sortie confondues."""
        return self.jetons_entree + self.jetons_sortie

    def vers_dict(self) -> dict:
        """Version sérialisable, pour le stockage et le rapport."""
        with self._verrou:
            return {"appels": self.appels, "jetons_entree": self.jetons_entree,
                    "jetons_sortie": self.jetons_sortie, "jetons": self.jetons,
                    "cout": self.cout, "par_modele": dict(self.par_modele)}


def compteurs_par_modele(compteurs: list[Compteur]) -> dict:
    """Agrège une liste de compteurs en un compteur unique."""
    total = Compteur()
    for compteur in compteurs:
        total.fusionner(compteur)
    return total.vers_dict()
