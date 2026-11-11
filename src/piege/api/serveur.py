"""Piège — serveur HTTP local et gestionnaire Lambda.

Deux expositions pour un même routeur :

- `python3 -m piege.api.serveur --port 8080` : serveur de démonstration, sert
  aussi le portail statique (`portal/`) ;
- `gestionnaire_lambda(evenement, contexte)` : adaptateur API Gateway / Lambda,
  sans dépendance tierce, pour le déploiement réel (lot 14).

Le serveur n'ajoute aucune logique métier : il traduit HTTP ↔ routeur.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from piege.api.contexte import Api, creer_api
from piege.api.routeur import router

__all__ = ["gestionnaire_lambda", "creer_gestionnaire", "servir",
           "DOSSIER_PORTAIL"]

DOSSIER_PORTAIL = "portal"
TYPES_STATIQUES = {".html": "text/html; charset=utf-8",
                   ".js": "application/javascript; charset=utf-8",
                   ".css": "text/css; charset=utf-8",
                   ".json": "application/json; charset=utf-8",
                   ".svg": "image/svg+xml", ".png": "image/png"}


def creer_gestionnaire(api: Optional[Api] = None):
    """Fabrique un gestionnaire HTTP lié à un contexte d'API."""
    contexte = api or creer_api()

    def gestionnaire(methode: str, chemin: str, corps: str,
                     entetes: dict) -> tuple[int, dict, str]:
        """Rend (statut, en-têtes, corps texte) pour une requête."""
        donnees = _decoder(corps)
        statut, reponse = router(methode, chemin, donnees, entetes, contexte)
        return statut, {"Content-Type": "application/json; charset=utf-8"}, \
            json.dumps(reponse, ensure_ascii=False)

    return gestionnaire


def _decoder(corps: str) -> dict:
    """Décode un corps JSON ; dictionnaire vide si absent ou invalide."""
    if not corps:
        return {}
    try:
        valeur = json.loads(corps)
    except json.JSONDecodeError:
        return {}
    return valeur if isinstance(valeur, dict) else {"valeur": valeur}


def gestionnaire_lambda(evenement: dict, contexte: Any = None) -> dict:
    """Adaptateur API Gateway (proxy v2 et v1) → réponse HTTP."""
    del contexte
    methode = evenement.get("requestContext", {}).get("http", {}).get("method") \
        or evenement.get("httpMethod", "GET")
    chemin = evenement.get("rawPath") or evenement.get("path", "/")
    requete = evenement.get("queryStringParameters") or {}
    if requete:
        from urllib.parse import urlencode

        chemin = "%s?%s" % (chemin, urlencode(requete))
    api = creer_api()
    gestionnaire = creer_gestionnaire(api)
    statut, entetes, corps = gestionnaire(methode, chemin,
                                          evenement.get("body") or "",
                                          evenement.get("headers") or {})
    return {"statusCode": statut, "headers": entetes, "body": corps,
            "isBase64Encoded": False}


class _Gestionnaire(BaseHTTPRequestHandler):
    """Gestionnaire HTTP du serveur de démonstration."""

    gestionnaire = None
    dossier_portail = DOSSIER_PORTAIL

    def do_GET(self):                                        # noqa: N802
        """GET : API ou fichier statique du portail."""
        if self.path.startswith("/api/"):
            return self._api("GET")
        return self._statique()

    def do_POST(self):                                       # noqa: N802
        """POST : API uniquement."""
        return self._api("POST")

    def do_PUT(self):                                        # noqa: N802
        """PUT : API uniquement."""
        return self._api("PUT")

    def do_DELETE(self):                                     # noqa: N802
        """DELETE : API uniquement."""
        return self._api("DELETE")

    def _api(self, methode: str):
        longueur = int(self.headers.get("Content-Length") or 0)
        corps = self.rfile.read(longueur).decode("utf-8") if longueur else ""
        statut, entetes, texte = self.gestionnaire(
            methode, self.path.replace("/api", "", 1) or "/", corps,
            dict(self.headers))
        self._repondre(statut, entetes, texte.encode("utf-8"))

    def _statique(self):
        """Sert le portail ; `/` renvoie `index.html`."""
        relatif = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        chemin = os.path.join(self.dossier_portail, relatif)
        if not os.path.isfile(chemin) or ".." in relatif:
            return self._repondre(404, {"Content-Type": "text/plain; charset=utf-8"},
                                  b"introuvable")
        with open(chemin, "rb") as f:
            contenu = f.read()
        extension = os.path.splitext(chemin)[1].lower()
        return self._repondre(200, {"Content-Type":
                                    TYPES_STATIQUES.get(extension,
                                                        "application/octet-stream")},
                              contenu)

    def _repondre(self, statut: int, entetes: dict, corps: bytes):
        self.send_response(statut)
        for cle, valeur in entetes.items():
            self.send_header(cle, valeur)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, format, *args):                    # noqa: A002
        """Journalisation minimale, sans bruit sur la sortie standard."""
        return None


def servir(port: int = 8080, api: Optional[Api] = None,
           dossier_portail: str = DOSSIER_PORTAIL) -> None:
    """Démarre le serveur de démonstration (bloquant)."""
    classe = type("GestionnairePiege", (_Gestionnaire,),
                  {"gestionnaire": creer_gestionnaire(api),
                   "dossier_portail": dossier_portail})
    serveur = ThreadingHTTPServer(("127.0.0.1", port), classe)
    print("Piège — API et portail sur http://127.0.0.1:%d/" % port)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        serveur.shutdown()


def main(argv: Optional[list[str]] = None) -> int:
    """Point d'entrée : `python3 -m piege.api.serveur --port 8080`."""
    analyseur = argparse.ArgumentParser(prog="piege.api.serveur")
    analyseur.add_argument("--port", type=int, default=8080)
    analyseur.add_argument("--portail", default=DOSSIER_PORTAIL)
    analyseur.add_argument("--donnees", default="donnees-locales")
    args = analyseur.parse_args(argv)
    os.environ.setdefault("PIEGE_DONNEES", args.donnees)
    servir(args.port, dossier_portail=args.portail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
