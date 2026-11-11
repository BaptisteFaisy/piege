"""Piège — fournisseur Bedrock : boto3 importé paresseusement.

Sans `boto3` ni identifiants AWS, le fournisseur lève
`FournisseurIndisponible` : le projet continue de tourner hors ligne, seule la
connexion réelle à Amazon Bedrock manque. Aucun secret n'est écrit dans le
dépôt, et le client n'est jamais journalisé.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from piege.erreurs import FournisseurIndisponible
from piege.fournisseurs.base import ReponseModele

__all__ = ["FournisseurBedrock", "MODELE_DEFAUT", "REGION_DEFAUT"]

MODELE_DEFAUT = "amazon.nova-lite-v1:0"
REGION_DEFAUT = "eu-west-3"
TEMPERATURE_JUGE = 0.0


def _extraire_json(texte: str) -> dict:
    """Extrait l'objet JSON d'une réponse Bedrock (fences éventuelles)."""
    from piege.fournisseurs.inferhub import extraire_json

    return extraire_json(texte)


class FournisseurBedrock:
    """Fournisseur Amazon Bedrock (API `converse`)."""

    nom = "bedrock"

    def __init__(self, modele: Optional[str] = None, region: Optional[str] = None,
                 client=None):
        self.modele = modele or os.environ.get("PIEGE_MODELE", MODELE_DEFAUT)
        self.region = region or os.environ.get("AWS_REGION", REGION_DEFAUT)
        self._client = client

    def client(self):
        """Client boto3 paresseux ; `FournisseurIndisponible` sans accès AWS."""
        if self._client is not None:
            return self._client
        try:
            import boto3                                       # noqa: PLC0415
        except ImportError as exc:
            raise FournisseurIndisponible(
                "boto3 absent : fournisseur Bedrock indisponible hors AWS",
                code="fournisseur_indisponible",
                details={"regle": "fournisseur.bedrock.client"}) from exc
        self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    @staticmethod
    def _messages(messages: list[dict]) -> list[dict]:
        """Convertit les messages au format Bedrock (rôles `user`/`assistant`)."""
        convertis = []
        for message in messages or []:
            role = "assistant" if message.get("role") == "assistant" else "user"
            convertis.append({"role": role,
                              "content": [{"text": str(message.get("content", ""))}]})
        return convertis

    def _converse(self, messages: list[dict], graine: int, max_jetons: int,
                  temperature: float) -> dict:
        """Appel Bedrock `converse`."""
        charge = {
            "modelId": self.modele,
            "messages": self._messages(messages),
            "inferenceConfig": {"maxTokens": max_jetons, "temperature": temperature},
        }
        try:
            return self.client().converse(**charge)
        except FournisseurIndisponible:
            raise
        except Exception as exc:                            # noqa: BLE001
            raise FournisseurIndisponible(
                "appel Bedrock impossible : %s" % str(exc)[:120],
                code="fournisseur_indisponible",
                details={"regle": "fournisseur.bedrock.appel"}) from exc

    @staticmethod
    def _texte(reponse: dict) -> str:
        """Extrait le texte de la réponse Bedrock."""
        try:
            blocs = reponse["output"]["message"]["content"]
            return "".join(bloc.get("text", "") for bloc in blocs)
        except (KeyError, TypeError) as exc:
            raise FournisseurIndisponible(
                "réponse Bedrock illisible",
                code="fournisseur_indisponible",
                details={"regle": "fournisseur.bedrock.reponse"}) from exc

    def completer(self, messages: list[dict], graine: int,
                  max_jetons: int = 1500, temperature: float = 0.0) -> ReponseModele:
        """Complétion libre."""
        reponse = self._converse(messages, graine, max_jetons, temperature)
        usage = reponse.get("usage") or {}
        return ReponseModele(
            texte=self._texte(reponse), jetons_entree=int(usage.get("inputTokens", 0)),
            jetons_sortie=int(usage.get("outputTokens", 0)), modele=self.modele,
            brut={"graine": graine})

    def sortie_structuree(self, messages: list[dict], schema: dict,
                          graine: int) -> dict:
        """Complétion dont la sortie doit être un objet JSON."""
        demande = list(messages) + [{"role": "user", "content": json.dumps(schema)}]
        reponse = self._converse(demande, graine, 1500, TEMPERATURE_JUGE)
        return _extraire_json(self._texte(reponse))
