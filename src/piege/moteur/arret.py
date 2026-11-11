"""Piège — arrêt d'urgence, suspension et reprise (EF-15, ENF-14).

Un geste suffit : `suspendre(campagne_id)`. Le moteur teste l'état **entre
chaque sonde**, donc l'effet est inférieur à la durée d'un échange (R5 exige
moins de 5 secondes). L'état est conservé : une campagne suspendue se reprend
là où elle s'est arrêtée, et une campagne interrompue par le budget garde ses
exécutions.
"""

from __future__ import annotations

import threading

from piege.types import maintenant_utc

__all__ = ["ArretUrgence", "suspendre", "reprendre", "arret_de", "RECORDS"]

RECORDS: dict = {}
_VERROU = threading.Lock()


class ArretUrgence:
    """Interrupteur d'une campagne : déclenché, levé, daté, motivé."""

    def __init__(self, actif: bool = False, motif: str = ""):
        self._actif = bool(actif)
        self._verrou = threading.Event()
        self.motif = motif
        self.declenche_le = maintenant_utc() if actif else ""
        if actif:
            self._verrou.set()

    @property
    def actif(self) -> bool:
        """État courant, lecture atomique."""
        return self._actif

    def declencher(self, motif: str = "arret demande") -> str:
        """Déclenche l'arrêt et rend l'horodatage (un geste, effet immédiat)."""
        with _VERROU:
            self._actif = True
            self.motif = motif
            self.declenche_le = maintenant_utc()
            self._verrou.set()
        return self.declenche_le

    def lever(self) -> None:
        """Lève l'arrêt : la campagne peut reprendre."""
        with _VERROU:
            self._actif = False
            self.motif = ""
            self.declenche_le = ""
            self._verrou.clear()

    def etat(self) -> dict:
        """État sérialisable, pour l'API et le portail."""
        return {"actif": self._actif, "motif": self.motif,
                "declenche_le": self.declenche_le}


def arret_de(campagne_id: str) -> ArretUrgence:
    """Interrupteur d'une campagne, créé au premier accès."""
    with _VERROU:
        if campagne_id not in RECORDS:
            RECORDS[campagne_id] = ArretUrgence()
        return RECORDS[campagne_id]


def suspendre(campagne_id: str, motif: str = "suspension demandee") -> ArretUrgence:
    """Suspend immédiatement une campagne en cours (EF-15)."""
    arret = arret_de(campagne_id)
    arret.declencher(motif)
    return arret


def reprendre(campagne_id: str) -> ArretUrgence:
    """Lève la suspension ; la campagne reprend avec son état conservé."""
    arret = arret_de(campagne_id)
    arret.lever()
    return arret


def oublier(campagne_id: str) -> None:
    """Oublie l'interrupteur d'une campagne terminée (ménage, tests)."""
    with _VERROU:
        RECORDS.pop(campagne_id, None)
