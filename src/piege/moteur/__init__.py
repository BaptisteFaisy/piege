"""Piège — moteur d'exécution des campagnes.

Point d'entrée public : `executer_campagne` (une campagne complète) et
`executer_technique` (rejeu d'une technique précise depuis un finding). Les
composants (mandat, cible, attaquant, juge, politique, entrepôt, fournisseur)
sont injectables : c'est ce qui permet de tout tester hors ligne.
"""

from piege.moteur.arret import ArretUrgence, reprendre, suspendre
from piege.moteur.budget import CompteurBudget
from piege.moteur.configuration import (ConfigurationCampagne,
                                        ConfigurationTechnique)
from piege.moteur.graine import (graine_technique, graine_tour, melanger,
                                 session_id)
from piege.moteur.orchestrateur import (Contexte, executer_campagne,
                                        executer_technique, preparer)

__all__ = [
    "executer_campagne", "executer_technique", "preparer", "Contexte",
    "ConfigurationCampagne", "ConfigurationTechnique", "CompteurBudget",
    "ArretUrgence", "suspendre", "reprendre", "graine_technique", "graine_tour",
    "session_id", "melanger",
]
