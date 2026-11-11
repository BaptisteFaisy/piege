"""Piège — reproductibilité : toutes les graines dérivent d'une seule.

Une campagne porte une graine entière. Tout choix dérivé (variante de sonde,
tour, identifiant de session, second passage du juge) est calculé à partir de
`hash_stable` (blake2b) et non de `hash()` de Python, qui est salé par
processus : sans cette précaution, deux campagnes identiques ne donneraient pas
le même verdict (ENF-05, KPI-8, R13).
"""

from __future__ import annotations

import random
from typing import Sequence, TypeVar

from piege.types import hash_stable

__all__ = ["graine_technique", "graine_tour", "graine_etiquetee", "choisir",
           "melanger", "session_id", "MASQUE_32"]

MASQUE_32 = 0xFFFFFFFF
_T = TypeVar("_T")


def graine_etiquetee(graine: int, etiquette: str) -> int:
    """Dérive une graine 32 bits stable d'une graine et d'une étiquette."""
    return (graine ^ hash_stable(etiquette)) & MASQUE_32


def graine_technique(graine: int, technique_id: str) -> int:
    """Graine propre à une technique dans une campagne."""
    return graine_etiquetee(graine, "technique:" + technique_id)


def graine_tour(graine: int, technique_id: str, tour: int) -> int:
    """Graine d'un tour donné d'une technique multi-tours."""
    return graine_etiquetee(graine_technique(graine, technique_id),
                            "tour:%d" % tour)


def session_id(graine: int, technique_id: str) -> str:
    """Identifiant de session isolée d'une technique (spécification §17.4)."""
    return "S-%s-%08x" % (technique_id, graine_technique(graine, technique_id))


def choisir(elements: Sequence[_T], graine: int, etiquette: str) -> _T:
    """Choisit déterministement un élément (jamais le hasard global)."""
    if not elements:
        raise ValueError("aucun élément à choisir")
    index = graine_etiquetee(graine, "choix:" + etiquette) % len(elements)
    return elements[index]


def melanger(elements: Sequence[_T], graine: int, etiquette: str) -> list:
    """Mélange déterministe : même graine, même ordre."""
    copie = list(elements)
    random.Random(graine_etiquetee(graine, "ordre:" + etiquette)).shuffle(copie)
    return copie
