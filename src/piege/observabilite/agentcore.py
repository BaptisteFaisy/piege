"""Piège — projection des traces sur AgentCore Observability / CloudWatch.

Les traces locales sont la référence : elles sont produites sans réseau et
suffisent au portail, au rapport et à Amazon Quick. Ce module les projette dans
le format attendu par AWS (OTLP-ish en dictionnaires purs, exportables en JSON)
et fournit un adaptateur qui les publie quand des identifiants AWS existent.

`boto3` est importé paresseusement : hors AWS, l'adaptateur lève une erreur
explicite au lieu d'échouer silencieusement.
"""

from __future__ import annotations

from typing import Optional

from piege.erreurs import FournisseurIndisponible
from piege.observabilite.compteurs import Compteur
from piege.observabilite.traces import traces

__all__ = ["vers_otlp", "AdaptateurObservability", "REGION_DEFAUT"]

REGION_DEFAUT = "eu-west-3"
SERVICE = "piege"


def vers_otlp(campagne_id: str, compteur: Optional[Compteur] = None) -> dict:
    """Convertit les traces d'une campagne en charge utile OTLP-like."""
    lignes = traces(campagne_id)
    return {
        "resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": SERVICE}},
                {"key": "campaign.id", "value": {"stringValue": campagne_id}},
            ]},
            "scopeSpans": [{
                "scope": {"name": "piege.moteur", "version": "1.0"},
                "spans": [_span(ligne) for ligne in lignes],
            }],
        }],
        "metrics": (compteur.vers_dict() if compteur is not None else {}),
    }


def _span(ligne: dict) -> dict:
    """Un span par trace : nom, durée, attributs."""
    return {
        "name": ligne.get("evenement") or "evenement",
        "startTimeUnixNano": 0,
        "endTimeUnixNano": int(ligne.get("duree_ms", 0)) * 1_000_000,
        "attributes": [
            {"key": "technique.id",
             "value": {"stringValue": str(ligne.get("technique_id", ""))}},
            {"key": "tenant.id",
             "value": {"stringValue": str(ligne.get("tenant_id", ""))}},
            {"key": "campaign.id",
             "value": {"stringValue": str(ligne.get("campagne_id", ""))}},
        ],
    }


class AdaptateurObservability:
    """Publication des traces vers AWS ; repli explicite hors AWS."""

    def __init__(self, client=None, region: str = REGION_DEFAUT,
                 groupe_journal: str = "/piege/campagnes"):
        self.region = region
        self.groupe_journal = groupe_journal
        self._client = client

    def client(self):
        """Client CloudWatch Logs (boto3 paresseux)."""
        if self._client is not None:
            return self._client
        try:
            import boto3                                       # noqa: PLC0415
        except ImportError as exc:
            raise FournisseurIndisponible(
                "boto3 absent : publication des traces impossible hors AWS",
                code="fournisseur_indisponible",
                details={"regle": "observabilite.client"}) from exc
        self._client = boto3.client("logs", region_name=self.region)
        return self._client

    def publier(self, campagne_id: str, lignes: Optional[list] = None) -> int:
        """Publie les traces d'une campagne ; rend le nombre d'événements."""
        import json

        evenements = lignes if lignes is not None else traces(campagne_id)
        if not evenements:
            return 0
        self.client().put_log_events(
            logGroupName=self.groupe_journal, logStreamName=campagne_id,
            logEvents=[{"timestamp": 0,
                        "message": json.dumps(e, ensure_ascii=False, sort_keys=True)}
                       for e in evenements])
        return len(evenements)

    def exporter(self, campagne_id: str, compteur: Optional[Compteur] = None) -> dict:
        """Charge utile OTLP prête à publier (utilisable hors ligne)."""
        return vers_otlp(campagne_id, compteur)
