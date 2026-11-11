"""Piège — cible HTTP : l'application du client derrière une API.

Transport **injectable** : les tests l'exercent hors ligne, sans réseau. La
cible est volontairement simple : elle poste une charge JSON et lit la réponse
en JSON. Aucune dépendance tierce (règle C3).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from piege.erreurs import ErreurPiege
from piege.types import Reponse

__all__ = ["CibleHttp", "TransportHttp"]

TransportHttp = Callable[[str, dict, int], dict]


class CibleHttp:
    """Cible HTTP : `POST {url}` avec `{requete, session, graine}`."""

    def __init__(self, spec: Optional[dict] = None,
                 transport: Optional[TransportHttp] = None):
        spec = dict(spec or {})
        self.id = str(spec.get("id", "APP-http"))
        self.application_id = str(spec.get("application_id", self.id))
        self.url = str(spec.get("url", ""))
        self.modele = str(spec.get("modele", "inconnu"))
        self.timeout = int(spec.get("timeout", 30))
        self.headers = dict(spec.get("headers") or {})
        self._transport = transport
        self._journal: list[dict] = []
        self._deposes: list[dict] = []

    def transport(self) -> TransportHttp:
        """Transport HTTP réel, sauf double injecté."""
        return self._transport or self._http

    def _http(self, url: str, charge: dict, graine: int) -> dict:
        """Appel HTTP réel (stdlib)."""
        requete = urllib.request.Request(
            url, data=json.dumps(charge).encode("utf-8"), method="POST")
        requete.add_header("Content-Type", "application/json")
        for cle, valeur in self.headers.items():
            requete.add_header(cle, valeur)
        try:
            with urllib.request.urlopen(requete, timeout=self.timeout) as reponse:
                return json.loads(reponse.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ErreurPiege("cible HTTP injoignable : %s" % str(exc)[:120],
                              code="cible_injoignable",
                              details={"regle": "cible.http"}) from exc
        except json.JSONDecodeError as exc:
            raise ErreurPiege("réponse HTTP illisible",
                              code="cible_injoignable",
                              details={"regle": "cible.http.json"}) from exc

    def sonder(self, demande: str, session: str, graine: int) -> Reponse:
        """Envoie une sonde et lit la réponse de l'application."""
        if not self.url:
            raise ErreurPiege("URL de cible absente", code="cible_injoignable",
                              details={"regle": "cible.http.url"})
        charge = {"requete": demande, "session": session, "graine": graine,
                  "modele": self.modele}
        brut = self.transport()(self.url, charge, graine)
        self.journaliser({"action": "sonde", "session": session})
        return self._envelopper(brut, session)

    def deposer_document(self, chemin: str, contenu: str, session: str) -> str:
        """Dépose un document (famille F) : appel de dépôt dédié."""
        if not self.url:
            raise ErreurPiege("URL de cible absente", code="cible_injoignable",
                              details={"regle": "cible.http.url"})
        charge = {"depot": chemin, "contenu": contenu, "session": session}
        brut = self.transport()(self.url, charge, 0)
        self._deposes.append({"chemin": chemin, "session": session})
        self.journaliser({"action": "depot", "chemin": chemin})
        return str(brut.get("document_id", chemin))

    def mesurer(self, requete: str, session: str) -> Reponse:
        """Mesure un effet sans compter comme une attaque."""
        enveloppe = self.sonder(requete, session, 0)
        enveloppe.brut["mesure"] = True
        return enveloppe

    def reindexer(self, session: str) -> None:
        """Réindexe l'index de la cible."""
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
        """Convertit la charge utile reçue en `Reponse`."""
        if not isinstance(brut, dict):
            raise ErreurPiege("réponse de cible illisible", code="cible_injoignable",
                              details={"regle": "cible.http.json"})
        texte = str(brut.get("texte") or brut.get("reponse") or "")
        return Reponse(texte=texte,
                       garde_fou_declenche=bool(brut.get("garde_fou", False)),
                       garde_fou_id=str(brut.get("garde_fou_id", "")),
                       jetons_entree=int(brut.get("jetons_entree", 0)),
                       jetons_sortie=int(brut.get("jetons_sortie", 0)),
                       latence_ms=int(brut.get("latence_ms", 0)),
                       brut=brut, session=session)
