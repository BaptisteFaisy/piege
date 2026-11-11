"""Piège — stockage : protocole d'entrepôt et fabrique.

Deux implémentations : `EntrepotLocal` (JSON sur disque, mode hors ligne par
défaut, utilisé par la CI et `make demo`) et `EntrepotDynamoDb` (boto3 importé
paresseusement, modèle de données du chapitre 19). Toutes deux garantissent le
filtrage par tenant (EF-60) et l'immuabilité des preuves.
"""

from __future__ import annotations

from typing import Optional, Protocol

from piege.types import Preuve

__all__ = ["Entrepot", "creer_entrepot", "TABLES"]

TABLES = ("tenants", "applications", "mandats", "campagnes", "executions",
          "findings", "correctifs", "preuves", "corpus_legitimes",
          "faux_refus", "journal")

PREFIXES = {
    "tenants": "TEN", "applications": "APP", "mandats": "MAN",
    "campagnes": "CMP", "executions": "EXE", "findings": "FINDING",
    "correctifs": "COR", "preuves": "PRV", "corpus_legitimes": "CORP",
    "faux_refus": "REF", "journal": "JRN",
}


class Entrepot(Protocol):
    """Contrat de stockage (CONTRACTS-INTERFACES §11)."""

    def ecrire(self, table: str, enregistrement: dict) -> str:
        """Écrit un enregistrement et retourne son identifiant."""

    def lire(self, table: str, identifiant: str, tenant_id: str = "") -> Optional[dict]:
        """Lit un enregistrement ; `None` s'il est absent ou d'un autre tenant."""

    def lister(self, table: str, tenant_id: str = "", **filtres) -> list[dict]:
        """Liste les enregistrements d'un tenant, filtrés."""

    def supprimer_tenant(self, tenant_id: str) -> Preuve:
        """Purge effective et prouvée d'un tenant (ENF-08, R20)."""

    def ecrire_journal(self, evenement: dict) -> str:
        """Ajoute une ligne au journal chaîné (append-only)."""


def creer_entrepot(spec: Optional[dict] = None) -> Entrepot:
    """Fabrique d'entrepôt : `local` par défaut, `dynamo` sur AWS."""
    spec = dict(spec or {})
    kind = spec.get("type", "local")
    if kind == "local":
        from piege.stockage.local import EntrepotLocal

        return EntrepotLocal(spec.get("dossier", "donnees-locales"))
    if kind == "dynamo":
        from piege.stockage.dynamo import EntrepotDynamoDb

        return EntrepotDynamoDb(spec.get("prefixe", "piege"),
                                spec.get("region", "eu-west-3"))
    raise ValueError("type d'entrepôt inconnu : %r" % kind)
