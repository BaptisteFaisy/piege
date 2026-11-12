"""Piège — rétention des données d'un tenant (ENF-08, R20).

La durée de rétention est une décision du client (`Tenant.retention_jours`) :
elle doit être **lue** et **opposable**, pas un champ mort. Ce module expose la
lecture de la durée et l'échéance qui en découle. La purge effective, elle, est
prouvée par `Entrepot.supprimer_tenant` (empreinte + fichier de preuve), routée
par `DELETE /tenants/{id}`.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

__all__ = ["DUREE_DEFAUT", "delai_retention", "expiration"]

DUREE_DEFAUT = 365


def delai_retention(entrepot: Any, tenant_id: str) -> int:
    """Durée de rétention du tenant (jours) ; `DUREE_DEFAUT` si inconnue."""
    record = entrepot.lire("tenants", tenant_id)
    valeur = (record or {}).get("retention_jours", DUREE_DEFAUT)
    try:
        return max(1, int(valeur))
    except (TypeError, ValueError):
        return DUREE_DEFAUT


def expiration(delai_jours: int, maintenant: Optional[str] = None) -> str:
    """Échéance de rétention (ISO) : `maintenant` moins `delai_jours` jours."""
    from piege.types import maintenant_utc

    brut = (maintenant or maintenant_utc()).replace("Z", "+00:00")
    instant = datetime.datetime.fromisoformat(brut)
    limite = instant - datetime.timedelta(days=max(1, delai_jours))
    return limite.isoformat().replace("+00:00", "Z")