"""Piège — API du portail (spécification §20).

Routeur en bibliothèque standard uniquement (règle C3), contexte injectable, et
deux modes d'exposition : un serveur HTTP local (`python3 -m piege.api.serveur`)
pour la démonstration, et un gestionnaire Lambda pour le déploiement réel
(lot 14). Le contrat de réponse est identique dans les deux cas :
`{"donnees": …}` en succès, `{"erreur": {code, message, regle}}` en échec.

La table de routes est assemblée dans `piege.api.ressources` (import différé
pour éviter tout cycle entre les modules de gestionnaires).
"""

from piege.api.contexte import Api, creer_api
from piege.api.routeur import correspondance, identite, router

__all__ = ["Api", "creer_api", "router", "identite", "correspondance", "routes"]


def routes() -> list:
    """Table de routes (méthode, motif, gestionnaire), chargée à la demande."""
    from piege.api import ressources

    return list(ressources.ROUTES)
