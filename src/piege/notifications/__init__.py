"""Piège — notifications Slack / Teams / webhook (#84).

Réduit le délai de fermeture (KPI-3) : un finding critique, une demande
d'approbation ou un arrêt d'urgence atteint la bonne personne en secondes.
Les messages sont normalisés (`evenements`), projetés par canal (`slack`,
`teams`) et dispensés en best-effort (`webhooks`). Aucune donnée sensible
(citation, preuve) n'est envoyée sur un canal de messagerie.
"""

from piege.notifications.evenements import (EVENEMENTS, SEVERITES_VISUELLES,
                                            TITRES, construire)
from piege.notifications.webhooks import (notifier, notifier_evenement, poster)

__all__ = ["construire", "EVENEMENTS", "TITRES", "SEVERITES_VISUELLES",
           "notifier", "notifier_evenement", "poster"]
