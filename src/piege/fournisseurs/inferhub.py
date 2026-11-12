"""Piège — fournisseur InferHub : HTTP compatible OpenAI, bibliothèque standard.

La clé ne sort jamais d'une variable d'environnement et n'est jamais journalisée.
Le transport est **injectable** : les tests l'exercent hors ligne, sans réseau.

Configuration (variables d'environnement) :
- `PIEGE_LLM_URL` : URL complète de l'endpoint (par défaut
  `https://api.inferhub.dev/v1/chat/completions`) ;
- `PIEGE_LLM_MODELE` : identifiant du modèle (par défaut `ag/gemini-3.8-flash-high`) ;
- `PIEGE_LLM_CLE` : clé d'API.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable, Optional

from piege.erreurs import FournisseurIndisponible
from piege.fournisseurs.base import ReponseModele

__all__ = ["FournisseurInferhub", "extraire_json", "objet_json",
           "URL_DEFAUT", "MODELE_DEFAUT"]

URL_DEFAUT = "https://api.inferhub.dev/v1/chat/completions"
MODELE_DEFAUT = "ag/gemini-3.8-flash-high"
# Un modèle qui raisonne met couramment 10 à 60 s par appel : 60 s de délai
# faisait échouer des campagnes réelles entières sur un seul appel lent.
TIMEOUT_DEFAUT = 180
TENTATIVES_DEFAUT = 2
# Sortie structurée : les modèles à raisonnement consomment une part du budget
# avant de produire l'objet. À 1 500 jetons, un verdict arrivait tronqué ou vide.
MAX_JETONS_SORTIE_DEFAUT = 4000
VAR_TIMEOUT = "PIEGE_LLM_TIMEOUT"
VAR_TENTATIVES = "PIEGE_LLM_TENTATIVES"
VAR_MAX_JETONS = "PIEGE_LLM_MAX_JETONS"


def objet_json(valeur) -> dict:
    """Normalise la sortie d'un modèle en objet JSON unique.

    Certains modèles enveloppent leur réponse dans un tableau (`[{…}]`) malgré
    la consigne : on déshabille un tableau à un seul objet, et sinon on retient
    l'objet qui porte la clé attendue. Rien n'est deviné au-delà.
    """
    if isinstance(valeur, dict):
        return valeur
    if isinstance(valeur, list):
        objets = [v for v in valeur if isinstance(v, dict)]
        if len(objets) == 1:
            return objets[0]
        for objet in objets:
            if "verdict" in objet:
                return objet
    raise FournisseurIndisponible(
        "sortie du modèle inexploitable : objet JSON attendu, reçu %s"
        % type(valeur).__name__, code="fournisseur_indisponible",
        details={"regle": "fournisseur.inferhub.json"})


def extraire_json(texte: str) -> dict:
    """Extrait l'objet JSON d'une réponse de modèle (fences, texte autour)."""
    if not texte:
        raise FournisseurIndisponible("réponse vide du modèle",
                                      code="fournisseur_indisponible",
                                      details={"regle": "fournisseur.inferhub.json"})
    nettoye = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", texte.strip())
    try:
        return objet_json(json.loads(nettoye))
    except json.JSONDecodeError:
        pass
    debut, fin = nettoye.find("{"), nettoye.rfind("}")
    if debut >= 0 and fin > debut:
        try:
            return objet_json(json.loads(nettoye[debut:fin + 1]))
        except json.JSONDecodeError as exc:
            raise FournisseurIndisponible(
                "sortie JSON illisible du modèle",
                code="fournisseur_indisponible",
                details={"regle": "fournisseur.inferhub.json"}) from exc
    raise FournisseurIndisponible("aucun objet JSON dans la réponse du modèle",
                                  code="fournisseur_indisponible",
                                  details={"regle": "fournisseur.inferhub.json"})


class FournisseurInferhub:
    """Client HTTP compatible OpenAI (InferHub), sans dépendance tierce."""

    nom = "inferhub"

    def __init__(self, url: Optional[str] = None, modele: Optional[str] = None,
                 cle: Optional[str] = None,
                 transport: Optional[Callable[[str, dict, str], dict]] = None,
                 timeout: Optional[int] = None, tentatives: Optional[int] = None,
                 max_jetons_sortie: Optional[int] = None):
        self.url = url or os.environ.get("PIEGE_LLM_URL", URL_DEFAUT)
        self.modele = modele or os.environ.get("PIEGE_LLM_MODELE", MODELE_DEFAUT)
        self.cle = cle if cle is not None else os.environ.get("PIEGE_LLM_CLE", "")
        # Un modèle qui raisonne met facilement 20 à 60 s à répondre : le délai
        # est configurable (PIEGE_LLM_TIMEOUT) et l'appel est rejoué
        # (PIEGE_LLM_TENTATIVES) — un timeout réseau n'est pas un verdict.
        self.timeout = int(timeout or os.environ.get("PIEGE_LLM_TIMEOUT",
                                                     TIMEOUT_DEFAUT))
        self.tentatives = max(1, int(tentatives or os.environ.get(
            "PIEGE_LLM_TENTATIVES", TENTATIVES_DEFAUT)))
        self.max_jetons_sortie = int(max_jetons_sortie or os.environ.get(
            "PIEGE_LLM_MAX_JETONS", MAX_JETONS_SORTIE_DEFAUT))
        self._transport = transport

    def transport(self) -> Callable[[str, dict, str], dict]:
        """Transport HTTP réel (urllib), sauf injection d'un double."""
        return self._transport or self._http

    def _http(self, url: str, charge: dict, cle: str) -> dict:
        """Appel HTTP réel : la clé n'est jamais journalisée."""
        requete = urllib.request.Request(url, data=json.dumps(charge).encode("utf-8"),
                                         method="POST")
        requete.add_header("Authorization", "Bearer " + cle)
        requete.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(requete, timeout=self.timeout) as reponse:
                return json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise FournisseurIndisponible(
                "InferHub a répondu %s" % exc.code, code="fournisseur_indisponible",
                details={"regle": "fournisseur.inferhub.http"}) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise FournisseurIndisponible(
                "InferHub injoignable : %s" % str(exc)[:120],
                code="fournisseur_indisponible",
                details={"regle": "fournisseur.inferhub.http"}) from exc

    def _charge(self, messages: list[dict], graine: int, max_jetons: int,
                temperature: float, json_attendu: bool) -> dict:
        """Construit la charge utile de l'API."""
        charge = {"model": self.modele, "messages": messages,
                  "max_tokens": max_jetons, "temperature": temperature}
        if json_attendu:
            charge["response_format"] = {"type": "json_object"}
        return charge

    def _appeler(self, messages: list[dict], graine: int, max_jetons: int,
                 temperature: float, json_attendu: bool) -> dict:
        """Appelle l'API et rend la réponse brute, avec nouvelles tentatives."""
        if not self.cle:
            raise FournisseurIndisponible(
                "clé absente : définir PIEGE_LLM_CLE (jamais dans le dépôt)",
                code="fournisseur_indisponible",
                details={"regle": "fournisseur.inferhub.cle"})
        charge = self._charge(messages, graine, max_jetons, temperature, json_attendu)
        derniere: Optional[Exception] = None
        for tentative in range(self.tentatives):
            try:
                return self.transport()(self.url, charge, self.cle)
            except FournisseurIndisponible as exc:
                derniere = exc
            except Exception as exc:                        # noqa: BLE001
                derniere = FournisseurIndisponible(
                    "appel InferHub impossible : %s" % str(exc)[:120],
                    code="fournisseur_indisponible",
                    details={"regle": "fournisseur.inferhub.appel",
                             "tentative": tentative + 1})
        raise derniere or FournisseurIndisponible(
            "appel InferHub épuisé", code="fournisseur_indisponible",
            details={"regle": "fournisseur.inferhub.appel"})

    @staticmethod
    def _contenu(reponse: dict) -> str:
        """Extrait le contenu textuel de la réponse OpenAI-compatible."""
        try:
            return reponse["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise FournisseurIndisponible(
                "réponse du modèle illisible (choices[0] absent)",
                code="fournisseur_indisponible",
                details={"regle": "fournisseur.inferhub.reponse"}) from exc

    def completer(self, messages: list[dict], graine: int,
                  max_jetons: int = 1500, temperature: float = 0.0) -> ReponseModele:
        """Complétion libre."""
        reponse = self._appeler(messages, graine, max_jetons, temperature, False)
        contenu = self._contenu(reponse)
        usage = reponse.get("usage") or {}
        brut = {"graine": graine, "modele_reel": reponse.get("model", "")}
        # Le routeur renvoie le coût réel de l'appel : on le conserve pour la
        # mesure exacte du KPI-7 (coût mesuré, jamais estimé).
        if usage.get("cost") is not None:
            brut["cout"] = float(usage["cost"])
        if usage.get("completion_tokens_details"):
            brut["raisonnement"] = usage["completion_tokens_details"].get(
                "reasoning_tokens", 0)
        return ReponseModele(
            texte=contenu, jetons_entree=int(usage.get("prompt_tokens", 0)),
            jetons_sortie=int(usage.get("completion_tokens", 0)),
            modele=self.modele, brut=brut)

    def sortie_structuree(self, messages: list[dict], schema: dict,
                          graine: int) -> dict:
        """Complétion dont la sortie doit être un objet JSON.

        Le budget de sortie est large : les modèles à raisonnement consomment
        une part des jetons pour leur chaîne de pensée avant de produire
        l'objet. À 1 500 jetons, un verdict pouvait arriver tronqué — voire
        vide — et faire échouer toute une campagne.
        """
        reponse = self._appeler(messages, graine, self.max_jetons_sortie, 0.0, True)
        return extraire_json(self._contenu(reponse))
