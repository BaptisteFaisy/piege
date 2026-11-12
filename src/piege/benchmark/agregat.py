"""Piège — benchmark inter-clients anonymisé (#41).

« Votre application est dans le 30e percentile du secteur finance pour la
résistance à l'injection. » Plus il y a de clients, plus la référence est riche,
plus le produit est différenciant : c'est une barrière à l'entrée par la donnée.

Règle de confidentialité stricte : le pool ne contient **jamais** d'identité
client. Chaque contribution porte une empreinte non réversible du tenant, un
secteur déclaré, un score de risque et une date. Aucun nom, aucune donnée de
découverte, aucune citation ne quitte le tenant. Un client ne voit que sa
position dans le pool, jamais les scores individuels des autres.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Optional

__all__ = ["Contribution", "empreinte_tenant", "construire_pool", "percentile",
           "statistiques", "comparer", "SECTEURS"]

SECTEURS = ("finance", "sante", "rh", "retail", "industrie", "public",
            "services", "tech", "autre")


@dataclass
class Contribution:
    """Une contribution anonymisée au pool de benchmark."""

    empreinte: str
    secteur: str
    score: int
    date: str

    def vers_dict(self) -> dict:
        """Version sérialisable (aucune donnée identifiante)."""
        return {"empreinte": self.empreinte, "secteur": self.secteur,
                "score": self.score, "date": self.date}


def empreinte_tenant(tenant_id: str, sel: str = "") -> str:
    """Empreinte non réversible d'un tenant : l'identité ne quitte jamais le SI."""
    return hashlib.sha256((sel + "|" + tenant_id).encode("utf-8")).hexdigest()[:16]


def construire_pool(contributions: Iterable[Contribution],
                    secteur: Optional[str] = None) -> list[Contribution]:
    """Filtre le pool sur un secteur (None = tous secteurs), trié par score."""
    pool = [c for c in contributions if secteur is None or c.secteur == secteur]
    return sorted(pool, key=lambda c: c.score)


def percentile(score: int, echantillon: Iterable[int]) -> float:
    """Rang percentile de `score` dans l'échantillon (0 = meilleur, 100 = pire).

    Un score de risque bas est bon : le percentile indique la part du pool qui
    fait **mieux** (score plus bas). Plus le percentile est bas, meilleure est
    l'application.
    """
    valeurs = sorted(echantillon)
    if not valeurs:
        return 0.0
    strictement_mieux = sum(1 for v in valeurs if v < score)
    egaux = sum(1 for v in valeurs if v == score)
    return round(100.0 * (strictement_mieux + 0.5 * egaux) / len(valeurs), 1)


def statistiques(echantillon: Iterable[int]) -> dict:
    """Moyenne, médiane et quartiles d'un pool de scores."""
    valeurs = sorted(echantillon)
    n = len(valeurs)
    if n == 0:
        return {"n": 0, "moyenne": 0.0, "mediane": 0.0, "min": 0, "max": 0,
                "q1": 0, "q3": 0}
    moyenne = sum(valeurs) / n
    return {"n": n, "moyenne": round(moyenne, 1), "mediane": _mediane(valeurs),
            "min": valeurs[0], "max": valeurs[-1],
            "q1": _quantile(valeurs, 0.25), "q3": _quantile(valeurs, 0.75)}


def _mediane(valeurs: list) -> float:
    n = len(valeurs)
    milieu = n // 2
    if n % 2:
        return float(valeurs[milieu])
    return (valeurs[milieu - 1] + valeurs[milieu]) / 2.0


def _quantile(valeurs: list, q: float) -> float:
    """Quantile par interpolation linéaire (q dans [0,1])."""
    if not valeurs:
        return 0.0
    position = q * (len(valeurs) - 1)
    bas = int(position)
    haut = min(bas + 1, len(valeurs) - 1)
    frac = position - bas
    return round(valeurs[bas] + (valeurs[haut] - valeurs[bas]) * frac, 1)


def comparer(score: int, pool: Iterable[Contribution],
             secteur: Optional[str] = None) -> dict:
    """Position d'une application dans le pool : percentile + repères."""
    contributions = construire_pool(pool, secteur)
    echantillon = [c.score for c in contributions]
    stats = statistiques(echantillon)
    rang = percentile(score, echantillon)
    return {
        "score": score,
        "secteur": secteur or "tous",
        "percentile": rang,
        "pool": stats,
        "meilleure_que_le_pool": score < stats["mediane"] if stats["n"] else None,
        "lecture": _lecture(rang, stats["n"]),
    }


def _lecture(percentile_rank: float, n: int) -> str:
    """Phrase lisible de positionnement (sans révéler de score tiers)."""
    if n == 0:
        return "pool vide : aucune comparaison possible"
    if percentile_rank <= 25:
        return "dans le quart le plus robuste du pool"
    if percentile_rank <= 50:
        return "au-dessus de la médiane du pool"
    if percentile_rank <= 75:
        return "sous la médiane du pool"
    return "dans le quart le plus exposé du pool"
