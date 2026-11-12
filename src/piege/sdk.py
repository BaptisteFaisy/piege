"""Piège — SDK Python de l'API (client mince, bibliothèque standard).

Même surface que l'API HTTP (spécification §20), sans dépendance tierce : le
transport est `urllib` par défaut et **injectable** pour les tests hors ligne.
Le jeton n'est jamais journalisé. Chaque méthode rend le champ `donnees` de la
réponse, ou lève `ErreurApi` (statut, code, message, règle) sur erreur.

Usage :

    from piege.sdk import Client
    client = Client("https://piege.exemple", "jeton:TEN-acme:analyste")
    mandat = client.signer_mandat(application_id="APP-1", ...)
    campagne = client.lancer_campagne(mandat["id"], graine=20261124)
    for finding in client.lister_findings(severite="critique"):
        ...
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

__all__ = ["Client", "ErreurApi", "Transport"]

# transport(methode, url, corps_octets, entetes) -> (statut, corps_texte)
Transport = Callable[[str, str, Optional[bytes], dict], tuple]
TIMEOUT = 60


class ErreurApi(Exception):
    """Erreur renvoyée par l'API (4xx/5xx), avec le code de domaine."""

    def __init__(self, statut: int, code: str, message: str, regle: str = ""):
        super().__init__(message)
        self.statut = statut
        self.code = code
        self.message = message
        self.regle = regle

    def vers_dict(self) -> dict:
        """Version sérialisable de l'erreur."""
        return {"statut": self.statut, "code": self.code,
                "message": self.message, "regle": self.regle}


def _transport_urllib(methode: str, url: str, corps: Optional[bytes],
                      entetes: dict) -> tuple:
    """Transport par défaut : urllib (bibliothèque standard)."""
    requete = urllib.request.Request(url, data=corps, method=methode)
    for cle, valeur in entetes.items():
        requete.add_header(cle, valeur)
    try:
        with urllib.request.urlopen(requete, timeout=TIMEOUT) as reponse:
            return reponse.status, reponse.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


class Client:
    """Client de l'API Piège. Le jeton porte le tenant : jamais en paramètre."""

    def __init__(self, base_url: str, jeton: str,
                 transport: Optional[Transport] = None, timeout: int = TIMEOUT):
        if not jeton:
            raise ValueError("un jeton d'identité est requis")
        self.base_url = (base_url or "").rstrip("/")
        self._jeton = jeton
        self._transport = transport or _transport_urllib
        self.timeout = timeout

    # ------------------------------------------------------------------ bas niveau
    def _requete(self, methode: str, chemin: str,
                 corps: Optional[dict] = None, requete: Optional[dict] = None) -> dict:
        """Exécute un appel ; rend `donnees` ou lève `ErreurApi`."""
        url = self.base_url + "/api" + chemin
        if requete:
            url += "?" + urllib.parse.urlencode(requete)
        octets = json.dumps(corps).encode("utf-8") if corps is not None else None
        entetes = {"Authorization": "Bearer " + self._jeton}
        if octets is not None:
            entetes["Content-Type"] = "application/json"
        statut, texte = self._transport(methode, url, octets, entetes)
        donnees = self._decoder(texte)
        if statut >= 400:
            erreur = (donnees or {}).get("erreur", {})
            raise ErreurApi(statut, erreur.get("code", "erreur"),
                            erreur.get("message", texte[:200]),
                            erreur.get("regle", ""))
        return (donnees or {}).get("donnees", donnees)

    @staticmethod
    def _decoder(texte: str) -> dict:
        """Décode un corps JSON ; dictionnaire vide si invalide."""
        if not texte:
            return {}
        try:
            return json.loads(texte)
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------ santé
    def sante(self) -> dict:
        """État du service, campagne en cours, budget restant."""
        return self._requete("GET", "/health")

    # ------------------------------------------------------------------ déclaration
    def declarer_application(self, **champs) -> dict:
        """Déclare une application cible (EF-01)."""
        return self._requete("POST", "/applications", champs)

    def signer_mandat(self, **champs) -> dict:
        """Crée et signe un mandat (EF-03)."""
        return self._requete("POST", "/mandats", champs)

    def mandat(self, identifiant: str) -> dict:
        """Lit un mandat et sa validité courante."""
        return self._requete("GET", "/mandats/%s" % identifiant)

    def charger_corpus_legitime(self, **champs) -> dict:
        """Charge le corpus de demandes légitimes (EF-30)."""
        return self._requete("POST", "/corpus-legitimes", champs)

    # ------------------------------------------------------------------ campagne
    def lancer_campagne(self, mandat_id: str, graine: int = 0, **champs) -> dict:
        """Lance une campagne (EF-10)."""
        corps = dict(champs)
        corps["mandat_id"] = mandat_id
        corps["graine"] = graine
        return self._requete("POST", "/campagnes", corps)

    def campagne(self, identifiant: str) -> dict:
        """Progression en direct d'une campagne."""
        return self._requete("GET", "/campagnes/%s" % identifiant)

    def executions(self, campagne_id: str) -> list:
        """Détail par technique d'une campagne."""
        return self._requete("GET", "/campagnes/%s/executions" % campagne_id)

    def suspendre(self, campagne_id: str, motif: str = "") -> dict:
        """Arrêt immédiat, état conservé (ENF-14)."""
        return self._requete("POST", "/campagnes/%s/suspendre" % campagne_id,
                             {"motif": motif})

    def reprendre(self, campagne_id: str) -> dict:
        """Reprise d'une campagne suspendue."""
        return self._requete("POST", "/campagnes/%s/reprendre" % campagne_id, {})

    def trancher(self, execution_id: str, decision: str, motif: str = "") -> dict:
        """Tranche un verdict ambigu en revue humaine (EF-22)."""
        return self._requete("POST", "/executions/%s/revue" % execution_id,
                             {"decision": decision, "motif": motif})

    # ------------------------------------------------------------------ découvertes
    def lister_findings(self, **filtres) -> list:
        """Liste les découvertes du tenant, filtrées (EF-62)."""
        return self._requete("GET", "/findings", requete=filtres or None)

    def finding(self, identifiant: str) -> dict:
        """Découverte complète avec preuves et correctifs."""
        return self._requete("GET", "/findings/%s" % identifiant)

    def proposer_correctifs(self, finding_id: str) -> list:
        """Génère les correctifs d'une découverte (EF-40)."""
        return self._requete("POST", "/findings/%s/correctifs" % finding_id, {})

    def autoriser_correctif(self, correctif_id: str, auteur: str, role: str,
                            **champs) -> dict:
        """Accord humain, application, rejeu et contrôles (EF-42/43)."""
        corps = dict(champs)
        corps.update({"auteur": auteur, "role": role})
        return self._requete("POST", "/correctifs/%s/autoriser" % correctif_id, corps)

    def rejouer(self, finding_id: str, **champs) -> dict:
        """Rejoue la technique d'origine depuis une découverte (EF-54)."""
        return self._requete("POST", "/findings/%s/rejouer" % finding_id,
                             champs or {})

    # ------------------------------------------------------------------ restitution
    def rapport(self, campagne_id: str, langue: str = "fr") -> dict:
        """Rapport client FR ou EN (EF-51)."""
        return self._requete("GET", "/rapports/%s" % campagne_id,
                             requete={"langue": langue})

    def attestation(self, campagne_id: str, langue: str = "fr") -> dict:
        """Attestation tierce, pauvre en détails (EF-53)."""
        return self._requete("GET", "/attestations/%s" % campagne_id,
                             requete={"langue": langue})

    def tendances(self, application_id: str) -> dict:
        """Taux de contournement et faux refus dans le temps (EF-52)."""
        return self._requete("GET", "/tendances/%s" % application_id)

    def budget(self) -> dict:
        """Coût mesuré par campagne et par tenant (EF-63, KPI-7)."""
        return self._requete("GET", "/budget")
