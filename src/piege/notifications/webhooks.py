"""Piège — dispersion des notifications et transport HTTP (#84).

`notifier` projette un événement normalisé sur tous les canaux configurés
(Slack, Teams, webhook générique). Le transport par défaut est un POST urllib
(bibliothèque standard) ; il est **injectable** pour les tests hors ligne. Les
URLs de webhook sont des secrets : jamais journalisées, jamais dans le corps
d'un message, et une erreur d'envoi ne bloque jamais la campagne (best-effort).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Optional

__all__ = ["poster", "notifier", "Transport"]

Transport = Callable[[str, dict], bool]
TIMEOUT = 10


def poster(url: str, charge: dict) -> bool:
    """Transport par défaut : POST JSON, rend True si 2xx."""
    if not url:
        return False
    donnees = json.dumps(charge, ensure_ascii=False).encode("utf-8")
    requete = urllib.request.Request(url, data=donnees, method="POST")
    requete.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(requete, timeout=TIMEOUT) as reponse:
            return 200 <= reponse.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def notifier(evenement: dict, config: Optional[dict] = None,
             transport: Optional[Transport] = None) -> dict:
    """Envoie un événement sur chaque canal configuré ; rend le détail par canal.

    `config` : dictionnaire canal → URL de webhook, parmi `slack`, `teams`,
    `webhook`. Un canal sans URL est ignoré. Best-effort : un échec est
    rapporté, jamais levé.
    """
    config = dict(config or {})
    transport = transport or poster
    resultat = {}
    if config.get("slack"):
        from piege.notifications import slack

        resultat["slack"] = slack.envoyer(config["slack"], evenement, transport)
    if config.get("teams"):
        from piege.notifications import teams

        resultat["teams"] = teams.envoyer(config["teams"], evenement, transport)
    if config.get("webhook"):
        resultat["webhook"] = bool(transport(config["webhook"], evenement))
    return resultat


def notifier_evenement(type_evenement: str, donnees: dict, config: Optional[dict] = None,
                       langue: str = "fr", base_url: str = "",
                       transport: Optional[Transport] = None) -> dict:
    """Construit puis dispense un événement en un appel."""
    from piege.notifications.evenements import construire

    evenement = construire(type_evenement, donnees, langue, base_url)
    return notifier(evenement, config, transport)
