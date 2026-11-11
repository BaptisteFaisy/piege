"""Piège — budget d'appels et de jetons, plafonné dans le code (ENF-02).

Le compteur est partagé entre les techniques d'une campagne exécutées en
parallèle : il est donc protégé par un verrou. Au seuil, la consommation est
**refusée** (elle n'est pas entamée) et l'appelant arrête proprement la
campagne en conservant l'état (R3).

Un budget non plafonné rend `None` (et non -1) : c'est la valeur que la
politique de périmètre attend pour ne pas contrôler ce budget.
"""

from __future__ import annotations

import threading
from typing import Optional

__all__ = ["CompteurBudget", "ILLIMITE"]

ILLIMITE = 0


class CompteurBudget:
    """Compteur thread-safe des appels et des jetons d'une campagne."""

    def __init__(self, appels_max: int = ILLIMITE, jetons_max: int = ILLIMITE):
        self.appels_max = max(0, int(appels_max))
        self.jetons_max = max(0, int(jetons_max))
        self.appels_consommes = 0
        self.jetons_consommes = 0
        self._verrou = threading.Lock()

    @staticmethod
    def _reste(consomme: int, maximum: int) -> Optional[int]:
        """Reste disponible ; `None` si le budget n'est pas plafonné."""
        if not maximum:
            return None
        return maximum - consomme

    def appels_restants(self) -> Optional[int]:
        """Appels restants, ou `None` si le budget n'est pas plafonné."""
        with self._verrou:
            return self._reste(self.appels_consommes, self.appels_max)

    def jetons_restants(self) -> Optional[int]:
        """Jetons restants, ou `None` si le budget n'est pas plafonné."""
        with self._verrou:
            return self._reste(self.jetons_consommes, self.jetons_max)

    def _peut(self, appels: int, jetons: int) -> bool:
        """Vrai si les deux budgets permettent la consommation demandée."""
        if appels:
            reste = self._reste(self.appels_consommes, self.appels_max)
            if reste is not None and reste < appels:
                return False
        if jetons:
            reste = self._reste(self.jetons_consommes, self.jetons_max)
            if reste is not None and reste < jetons:
                return False
        return True

    def peut_consommer(self, appels: int = 0, jetons: int = 0) -> bool:
        """Vrai si le budget permet la consommation demandée."""
        with self._verrou:
            return self._peut(appels, jetons)

    def consommer(self, appels: int = 1, jetons: int = 0) -> bool:
        """Consomme si le budget le permet ; sinon ne touche à rien."""
        with self._verrou:
            if not self._peut(appels, jetons):
                return False
            self.appels_consommes += appels
            self.jetons_consommes += jetons
            return True

    def epuise(self) -> bool:
        """Vrai si au moins un des deux budgets est à zéro."""
        with self._verrou:
            return not self._peut(1, 0) or not self._peut(0, 1)

    def restants(self) -> dict:
        """État complet, pour la politique et pour l'observabilité."""
        with self._verrou:
            return {"appels_restants": self._reste(self.appels_consommes,
                                                   self.appels_max),
                    "jetons_restants": self._reste(self.jetons_consommes,
                                                   self.jetons_max),
                    "appels_consommes": self.appels_consommes,
                    "jetons_consommes": self.jetons_consommes}
