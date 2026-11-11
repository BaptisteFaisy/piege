"""Piège — entrepôt DynamoDB (déploiement réel).

`boto3` est importé **paresseusement** : sans lui, ou sans identifiants AWS,
l'entrepôt lève `FournisseurIndisponible` et le reste du projet continue de
tourner hors ligne. Le modèle de données suit le chapitre 19 de la
spécification : clé de partition `id`, index sur `tenant_id` (isolation EF-60),
journal en table séparée append-only.
"""

from __future__ import annotations

from typing import Optional

from piege.erreurs import FournisseurIndisponible
from piege.stockage.base import TABLES
from piege.types import Preuve, maintenant_utc

__all__ = ["EntrepotDynamoDb"]


class EntrepotDynamoDb:
    """Entrepôt DynamoDB : mêmes garanties que l'entrepôt local."""

    def __init__(self, prefixe: str = "piege", region: str = "eu-west-3",
                 client=None):
        self.prefixe = prefixe
        self.region = region
        self._client = client

    def client(self):
        """Client boto3 paresseux ; `FournisseurIndisponible` s'il est absent."""
        if self._client is not None:
            return self._client
        try:
            import boto3                                       # noqa: PLC0415
        except ImportError as exc:
            raise FournisseurIndisponible(
                "boto3 absent : entrepôt DynamoDB indisponible hors AWS",
                code="fournisseur_indisponible",
                details={"regle": "stockage.client"}) from exc
        self._client = boto3.client("dynamodb", region_name=self.region)
        return self._client

    def nom_table(self, table: str) -> str:
        """Nom physique de la table préfixée (validation du nom logique)."""
        if table not in TABLES:
            raise FournisseurIndisponible("table inconnue : %r" % table,
                                          code="table_inconnue")
        return "%s-%s" % (self.prefixe, table)

    def ecrire(self, table: str, enregistrement: dict) -> str:
        """Écrit un item ; l'identifiant doit être fourni par l'appelant."""
        identifiant = enregistrement.get("id")
        if not identifiant:
            raise FournisseurIndisponible(
                "l'identifiant est alloué par le moteur, jamais par DynamoDB",
                code="identifiant_absent")
        self.client().put_item(TableName=self.nom_table(table),
                               Item=_vers_item(enregistrement))
        return str(identifiant)

    def lire(self, table: str, identifiant: str, tenant_id: str = "") -> Optional[dict]:
        """Lit un item et vérifie le tenant (EF-60)."""
        reponse = self.client().get_item(TableName=self.nom_table(table),
                                         Key={"id": {"S": str(identifiant)}})
        item = reponse.get("Item")
        if not item:
            return None
        donnees = _depuis_item(item)
        if tenant_id and donnees.get("tenant_id") not in (None, tenant_id):
            return None
        return donnees

    def lister(self, table: str, tenant_id: str = "", **filtres) -> list[dict]:
        """Balayage filtré par tenant (index `tenant_id` en production)."""
        expression, valeurs = _filtres(filtres, tenant_id)
        reponse = self.client().scan(TableName=self.nom_table(table),
                                     FilterExpression=expression,
                                     ExpressionAttributeValues=valeurs)
        return [_depuis_item(item) for item in reponse.get("Items", [])]

    def ecrire_journal(self, evenement: dict) -> str:
        """Ajoute une ligne au journal chaîné (append-only)."""
        evenement = dict(evenement)
        evenement.setdefault("id", "JRN-%s" % maintenant_utc().replace(":", ""))
        return self.ecrire("journal", evenement)

    def supprimer_tenant(self, tenant_id: str) -> Preuve:
        """Purge par tenant ; l'implémentation réelle itère les 10 tables."""
        raise FournisseurIndisponible(
            "purge DynamoDB à câbler au déploiement (S3) : itération par index "
            "tenant_id puis preuve de purge", code="non_implemente")


def _vers_item(enregistrement: dict) -> dict:
    """Convertit un enregistrement en item DynamoDB (types simples)."""
    item = {}
    for cle, valeur in enregistrement.items():
        if isinstance(valeur, bool):
            item[cle] = {"BOOL": valeur}
        elif isinstance(valeur, (int, float)):
            item[cle] = {"N": str(valeur)}
        elif isinstance(valeur, list):
            item[cle] = {"L": [_vers_valeur(v) for v in valeur]}
        elif isinstance(valeur, dict):
            item[cle] = {"M": _vers_item(valeur)}
        else:
            item[cle] = {"S": str(valeur if valeur is not None else "")}
    return item


def _vers_valeur(valeur):
    """Convertit une valeur isolée d'une liste."""
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return {"N": str(valeur)}
    return {"S": str(valeur)}


def _depuis_item(item: dict) -> dict:
    """Convertit un item DynamoDB en dictionnaire Python simple."""
    sortie = {}
    for cle, valeur in item.items():
        if "S" in valeur:
            sortie[cle] = valeur["S"]
        elif "N" in valeur:
            sortie[cle] = float(valeur["N"]) if "." in valeur["N"] else int(valeur["N"])
        elif "BOOL" in valeur:
            sortie[cle] = valeur["BOOL"]
        elif "L" in valeur:
            sortie[cle] = [list(v.values())[0] for v in valeur["L"]]
        elif "M" in valeur:
            sortie[cle] = _depuis_item(valeur["M"])
    return sortie


def _filtres(filtres: dict, tenant_id: str) -> tuple[str, dict]:
    """Construit une expression de filtrage DynamoDB (égalité stricte)."""
    conditions, valeurs = [], {}
    if tenant_id:
        conditions.append("#tenant = :tenant")
        valeurs[":tenant"] = {"S": tenant_id}
    for index, (cle, attendue) in enumerate(filtres.items()):
        conditions.append("#f%d = :f%d" % (index, index))
        valeurs[":f%d" % index] = {"S": str(attendue)}
    return " AND ".join(conditions) or None, valeurs
