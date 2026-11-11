"""Piège — traces structurées et compteurs par campagne.

Chaque événement de campagne (ouverture, sonde, verdict, refus, fin) est tracé
avec sa durée et son tenant. Les traces sont exportables en JSON Lines pour
Amazon Quick et pour AgentCore Observability (lot 13 et lot 14). Aucun `print`
brut : tout passe par `tracer`, ce qui rend la journalisation exploitable.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from piege.observabilite.compteurs import Compteur
from piege.types import maintenant_utc

__all__ = ["tracer", "compte", "nouveau_compteur", "traces", "Trace",
           "exporter_jsonl", "reinitialiser"]

_REGISTRE: dict[str, Compteur] = {}
_TRACES: dict[str, list[dict]] = {}


def reinitialiser() -> None:
    """Vide registres et traces (tests uniquement)."""
    _REGISTRE.clear()
    _TRACES.clear()


def nouveau_compteur(campagne_id: str) -> Compteur:
    """Crée (ou remplace) le compteur d'une campagne."""
    compteur = Compteur()
    _REGISTRE[campagne_id] = compteur
    _TRACES.setdefault(campagne_id, [])
    return compteur


def compte(campagne_id: str) -> Compteur:
    """Compteur d'une campagne, créé au premier accès."""
    if campagne_id not in _REGISTRE:
        return nouveau_compteur(campagne_id)
    return _REGISTRE[campagne_id]


def tracer(evenement: dict, campagne_id: str = "", duree_ms: int = 0) -> dict:
    """Journalise un événement structuré et le rend (pour l'appelant)."""
    trace = {
        "date": maintenant_utc(),
        "campagne_id": campagne_id or str(evenement.get("campagne_id", "")),
        "technique_id": evenement.get("technique_id", ""),
        "tenant_id": evenement.get("tenant_id", ""),
        "evenement": evenement.get("evenement", ""),
        "duree_ms": duree_ms,
        "details": {k: v for k, v in evenement.items()
                    if k not in ("campagne_id", "technique_id", "tenant_id",
                                 "evenement")},
    }
    _TRACES.setdefault(trace["campagne_id"], []).append(trace)
    return trace


def traces(campagne_id: str) -> list[dict]:
    """Copie des traces d'une campagne, dans l'ordre d'émission."""
    return [dict(trace) for trace in _TRACES.get(campagne_id, [])]


class Trace:
    """Contexte de mesure d'une phase : `with Trace(...) as t: ...`."""

    def __init__(self, campagne_id: str, evenement: str,
                 technique_id: str = "", tenant_id: str = ""):
        self.campagne_id = campagne_id
        self.evenement = evenement
        self.technique_id = technique_id
        self.tenant_id = tenant_id
        self._depart: Optional[float] = None
        self.duree_ms = 0
        self.trace: dict = {}

    def __enter__(self) -> "Trace":
        self._depart = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.duree_ms = int((time.monotonic() - (self._depart or 0)) * 1000)
        self.trace = tracer({
            "evenement": self.evenement, "campagne_id": self.campagne_id,
            "technique_id": self.technique_id, "tenant_id": self.tenant_id,
            "erreur": "" if exc_type is None else str(exc)[:200],
        }, campagne_id=self.campagne_id, duree_ms=self.duree_ms)
        return False


def exporter_jsonl(campagne_id: str, chemin: str) -> int:
    """Écrit les traces d'une campagne en JSON Lines ; rend le nombre de lignes."""
    lignes = traces(campagne_id)
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        for trace in lignes:
            f.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")
    return len(lignes)
