"""Piège — sortie de client : purge d'un tenant, avec preuve (ENF-08, R20).

`docs/RUNBOOK.md` annonce `DELETE /tenants/{id}` depuis le début ; la purge
était implémentée dans l'entrepôt mais **jamais routée**. Cette route la rend
accessible, avec la preuve de purge (empreinte + fichier) et la durée de
rétention du tenant, désormais lue — plus un champ mort.

Règle d'identité (EF-61) : un client (`commanditaire`) ne peut purger que son
propre tenant ; l'analyste MSP purifie n'importe quel tenant de la flotte.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.api.aides import exiger_role
from piege.securite import retention

__all__ = ["ROUTES", "supprimer_tenant_route"]

ROLES_PURGE = ("commanditaire", "analyste")


def supprimer_tenant_route(api: Any, tenant: str, roles: list, id: str,
                           requete: Optional[dict] = None, **_) -> dict:
    """Purge toutes les données d'un tenant et rend la preuve datée."""
    del requete
    exiger_role(roles, list(ROLES_PURGE), "purger les données d'un tenant")
    if tenant != id and "analyste" not in roles:
        from piege.erreurs import RoleInsuffisant

        raise RoleInsuffisant(
            "un client ne peut purger que son propre tenant",
            details={"regle": "api.tenant"})
    delai = retention.delai_retention(api.entrepot, id)
    preuve = api.entrepot.supprimer_tenant(id)
    api.entrepot.ecrire_journal({"qui": "api", "quoi": "tenant_purge",
                                 "tenant": id,
                                 "details": {"preuve": preuve.id,
                                             "retention_jours": delai},
                                 "marqueur": "trafic_reel"})
    return {"tenant_id": id, "preuve": preuve.vers_dict(),
            "retention_jours": delai, "expire_le": retention.expiration(delai)}


ROUTES = [("DELETE", "/tenants/{id}", supprimer_tenant_route)]