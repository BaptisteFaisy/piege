"""Piège — table de routes de l'API (spécification §20).

Les gestionnaires sont répartis en quatre modules thématiques ; ce fichier
n'assemble que la table `ROUTES`, consommée par le routeur. Les utilitaires
partagés vivent dans `piege.api.aides` afin d'éviter tout cycle d'import.
"""

from __future__ import annotations

from piege.api.aides import (ecrire, exiger_role, introuvable, lire,
                             lire_ou_erreur)
from piege.api.ressources_campagnes import ROUTES as ROUTES_CAMPAGNES
from piege.api.ressources_evolutions import ROUTES as ROUTES_EVOLUTIONS
from piege.api.ressources_export import ROUTES as ROUTES_EXPORT
from piege.api.ressources_findings import ROUTES as ROUTES_FINDINGS
from piege.api.ressources_mandats import ROUTES as ROUTES_MANDATS
from piege.api.ressources_rapports import ROUTES as ROUTES_RAPPORTS

__all__ = ["ROUTES", "lire", "lire_ou_erreur", "ecrire", "exiger_role",
           "introuvable", "chemins"]

ROUTES = (ROUTES_MANDATS + ROUTES_CAMPAGNES + ROUTES_FINDINGS
          + ROUTES_RAPPORTS + ROUTES_EVOLUTIONS + ROUTES_EXPORT)


def chemins() -> list:
    """Liste des routes exposées, pour la documentation et le portail."""
    return ["%s %s" % (methode, motif) for methode, motif, _ in ROUTES]
