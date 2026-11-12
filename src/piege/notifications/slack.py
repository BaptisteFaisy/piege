"""Piège — projection Slack (Block Kit) et envoi (#84).

Le webhook Slack est un secret d'URL : il n'est jamais journalisé, jamais écrit
dans le dépôt, et l'envoi passe par un transport **injectable** pour rester
testable hors ligne.
"""

from __future__ import annotations

from typing import Callable, Optional

__all__ = ["payload", "envoyer"]

Transport = Callable[[str, dict], bool]


def payload(evenement: dict) -> dict:
    """Construit le message Slack (Block Kit) d'un événement normalisé."""
    blocs = [
        {"type": "header",
         "text": {"type": "plain_text", "text": evenement["titre"],
                  "emoji": True}},
        {"type": "section",
         "text": {"type": "mrkdwn", "text": evenement["texte"]}},
    ]
    champs = evenement.get("donnees") or {}
    if champs:
        blocs.append({"type": "section", "fields": [
            {"type": "mrkdwn", "text": "*%s*\n%s" % (cle, valeur)}
            for cle, valeur in list(champs.items())[:8]]})
    if evenement.get("lien"):
        blocs.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Ouvrir"},
             "url": evenement["lien"], "style": "primary"}]})
    return {"text": "%s — %s" % (evenement["titre"], evenement["texte"]),
            "blocks": blocs,
            "attachments": [{"color": evenement.get("couleur", "#00703c"),
                             "fallback": evenement["titre"]}]}


def envoyer(webhook_url: str, evenement: dict, transport: Optional[Transport] = None) -> bool:
    """Envoie l'événement sur Slack ; rend le succès booléen."""
    from piege.notifications.webhooks import poster

    if not webhook_url:
        return False
    transport = transport or poster
    return bool(transport(webhook_url, payload(evenement)))
