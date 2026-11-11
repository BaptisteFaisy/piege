"""Piège — index de test isolé pour la famille F (EF-17).

Chaque campagne crée son propre index, y dépose ses documents piégés, mesure,
puis le détruit. Le corpus du client n'est jamais touché : c'est la condition
pour que le service soit vendable à un RSSI.

Le contexte `index_isole` garantit la destruction même en cas d'erreur — la
destruction est dans un `finally`, pas dans le chemin nominal.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from piege.types import Mandat, maintenant_utc

__all__ = ["creer_index_test", "detruire", "index_isole", "PREFIXE_INDEX"]

PREFIXE_INDEX = "idx-test"


def creer_index_test(cible: Any, mandat: Mandat, campagne_id: str = "",
                     session: str = "") -> str:
    """Crée (ou désigne) l'index de test d'une campagne et le journalise."""
    identifiant = "%s-%s-%s" % (PREFIXE_INDEX, campagne_id or mandat.id,
                                session or "default")
    cible.journaliser({"action": "creation_index_test", "index": identifiant,
                       "mandat": mandat.id, "date": maintenant_utc()})
    return identifiant


def detruire(cible: Any, index_id: str) -> None:
    """Détruit l'index de test : plus aucune trace des dépôts (R7)."""
    cible.detruire_index(index_id)
    cible.journaliser({"action": "destruction_index_test", "index": index_id,
                       "date": maintenant_utc()})


@contextmanager
def index_isole(cible: Any, mandat: Mandat, campagne_id: str = "",
                session: str = ""):
    """Contexte d'exécution : crée l'index, le rend, puis le détruit toujours."""
    index_id = creer_index_test(cible, mandat, campagne_id, session)
    try:
        yield index_id
    finally:
        detruire(cible, index_id)
