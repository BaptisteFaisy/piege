"""Piège — cible Amazon Bedrock : assistant RAG sur Knowledge Bases.

Squelette d'adaptateur : `boto3` est importé **paresseusement**, et sans lui
(ou sans identifiants AWS) la cible lève une erreur explicite au lieu de
mentir. La boucle réelle — appel Bedrock, garde-fous, base de connaissances,
mesure des jetons — est câblée au moment du déploiement (lot 14).
"""

from __future__ import annotations

from typing import Optional

from piege.erreurs import ErreurPiege
from piege.types import Reponse

__all__ = ["CibleBedrock", "REGION_DEFAUT"]

REGION_DEFAUT = "eu-west-3"


class CibleBedrock:
    """Cible Amazon Bedrock : InvokeModel + Guardrails + Knowledge Bases."""

    def __init__(self, spec: Optional[dict] = None, client=None):
        spec = dict(spec or {})
        self.id = str(spec.get("id", "APP-bedrock"))
        self.application_id = str(spec.get("application_id", self.id))
        self.modele = str(spec.get("modele", "amazon.nova-lite-v1:0"))
        self.region = str(spec.get("region", REGION_DEFAUT))
        self.garde_fou_id = str(spec.get("garde_fou_id", ""))
        self.base_connaissance = str(spec.get("knowledge_base_id", ""))
        self._client = client
        self._journal: list[dict] = []

    def client(self):
        """Client boto3 paresseux ; erreur explicite sans accès AWS."""
        if self._client is not None:
            return self._client
        try:
            import boto3                                       # noqa: PLC0415
        except ImportError as exc:
            raise ErreurPiege("boto3 absent : cible Bedrock indisponible hors AWS",
                              code="cible_injoignable",
                              details={"regle": "cible.bedrock.client"}) from exc
        self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def sonder(self, demande: str, session: str, graine: int) -> Reponse:
        """Interroge Bedrock avec la garde-fou et la base de connaissance."""
        charge = {
            "modelId": self.modele,
            "messages": [{"role": "user", "content": [{"text": demande}]}],
        }
        if self.garde_fou_id:
            charge["guardrailIdentifier"] = self.garde_fou_id
        if self.base_connaissance:
            charge["knowledgeBaseId"] = self.base_connaissance
        try:
            brut = self.client().converse(**charge)
        except Exception as exc:                            # noqa: BLE001
            raise ErreurPiege("appel Bedrock impossible : %s" % str(exc)[:120],
                              code="cible_injoignable",
                              details={"regle": "cible.bedrock.appel"}) from exc
        self.journaliser({"action": "sonde", "session": session})
        return self._envelopper(brut, session)

    def deposer_document(self, chemin: str, contenu: str, session: str) -> str:
        """Dépose un document : ingestion Knowledge Bases (à câbler)."""
        raise ErreurPiege("dépôt Knowledge Bases à câbler au déploiement (S3)",
                          code="cible_injoignable",
                          details={"regle": "cible.bedrock.depot"})

    def mesurer(self, requete: str, session: str) -> Reponse:
        """Mesure un effet sans compter comme une attaque."""
        enveloppe = self.sonder(requete, session, 0)
        enveloppe.brut["mesure"] = True
        return enveloppe

    def reindexer(self, session: str) -> None:
        """Réindexe la base de connaissance."""
        self.journaliser({"action": "reindexation", "session": session})

    def detruire_index(self, index_id: str) -> None:
        """Détruit l'index de test."""
        self.journaliser({"action": "destruction_index", "index": index_id})

    def journaliser(self, evenement: dict) -> None:
        """Journalise un événement côté cible."""
        self._journal.append(dict(evenement))

    @property
    def journal(self) -> list[dict]:
        """Copie du journal de la cible."""
        return [dict(ligne) for ligne in self._journal]

    def _envelopper(self, brut: dict, session: str) -> Reponse:
        """Convertit la réponse Bedrock en `Reponse`."""
        usage = brut.get("usage") or {}
        texte = ""
        message = (brut.get("output") or {}).get("message", {})
        for bloc in message.get("content", []):
            texte += bloc.get("text", "")
        return Reponse(texte=texte,
                       garde_fou_declenche=bool(
                           (brut.get("guardrail") or {}).get("action")),
                       jetons_entree=int(usage.get("inputTokens", 0)),
                       jetons_sortie=int(usage.get("outputTokens", 0)),
                       brut=brut, session=session)
