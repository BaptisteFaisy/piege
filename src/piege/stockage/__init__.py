"""Piège — stockage : entrepôts local (JSON) et DynamoDB.

`creer_entrepot` est le point d'entrée unique ; les implémentations sont
importées paresseusement pour garder le cœur sans dépendance tierce.
"""

from piege.stockage.base import PREFIXES, TABLES, Entrepot, creer_entrepot

__all__ = ["Entrepot", "creer_entrepot", "TABLES", "PREFIXES"]
