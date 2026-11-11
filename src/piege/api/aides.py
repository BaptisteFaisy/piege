"""Piège — utilitaires partagés des gestionnaires de routes.

Module sans dépendance vers les gestionnaires : c'est lui qui casse le cycle
d'import entre la table de routes et les modules thématiques. Il porte les deux
garde-fous transverses de l'API : toute lecture est filtrée par tenant
(EF-60) et toute action exige un rôle habilité (spécification §7).
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["lire", "lire_ou_erreur", "ecrire", "exiger_role", "introuvable"]


def introuvable(quoi: str, identifiant: str):
    """Erreur 404 homogène, qui ne révèle rien d'un autre tenant."""
    from piege.erreurs import Introuvable

    return Introuvable("%s %s introuvable" % (quoi, identifiant),
                       details={"regle": "api.introuvable", "id": identifiant})


def lire(api: Any, table: str, identifiant: str, tenant: str) -> Optional[dict]:
    """Lecture filtrée par tenant : un autre tenant obtient `None` (EF-60)."""
    return api.entrepot.lire(table, identifiant, tenant_id=tenant)


def lire_ou_erreur(api: Any, table: str, identifiant: str, tenant: str) -> dict:
    """Lecture filtrée, avec 404 explicite si absente ou d'un autre tenant."""
    enregistrement = lire(api, table, identifiant, tenant)
    if enregistrement is None:
        raise introuvable(table, identifiant)
    return enregistrement


def ecrire(api: Any, table: str, enregistrement: dict) -> str:
    """Écriture dans l'entrepôt."""
    return api.entrepot.ecrire(table, enregistrement)


def exiger_role(roles_du_jet: list, autorises: list, action: str) -> None:
    """Vérifie l'habilitation ; refus 403 journalisable sinon."""
    from piege.erreurs import RoleInsuffisant

    if not set(autorises).intersection(roles_du_jet):
        raise RoleInsuffisant(
            "rôle insuffisant pour %s (%s requis)" % (action, "/".join(autorises)),
            details={"regle": "api.role"})
