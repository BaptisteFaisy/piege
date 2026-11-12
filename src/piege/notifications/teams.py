"""Piège — projection Microsoft Teams (MessageCard) et envoi (#84).

Même contrat que Slack : webhook secret jamais journalisé, transport injectable,
testable hors ligne. Teams utilise le format MessageCard (connecteur webhook
entrant).
"""

from __future__ import annotations

from typing import Callable, Optional

__all__ = ["payload", "envoyer"]

Transport = Callable[[str, dict], bool]


def payload(evenement: dict) -> dict:
    """Construit la carte Teams d'un événement normalisé."""
    faits = [{"name": cle, "value": str(valeur)}
             for cle, valeur in (evenement.get("donnees") or {}).items()]
    actions = []
    if evenement.get("lien"):
        actions.append({"@type": "OpenUri", "name": "Ouvrir dans Piège",
                        "targets": [{"os": "default", "uri": evenement["lien"]}]})
    carte = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": evenement["titre"],
        "themeColor": evenement.get("couleur", "00703c").lstrip("#"),
        "title": evenement["titre"],
        "text": evenement["texte"],
    }
    if faits:
        carte["sections"] = [{"activityTitle": evenement["titre"], "facts": faits}]
    if actions:
        carte["potentialAction"] = actions
    return carte


def envoyer(webhook_url: str, evenement: dict, transport: Optional[Transport] = None) -> bool:
    """Envoie l'événement sur Teams ; rend le succès booléen."""
    from piege.notifications.webhooks import poster

    if not webhook_url:
        return False
    transport = transport or poster
    return bool(transport(webhook_url, payload(evenement)))
