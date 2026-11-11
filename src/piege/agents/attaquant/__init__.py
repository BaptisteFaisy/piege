"""Piège — agent attaquant : exécution bornée, variantes, outils, adaptateur.

L'agent ne connaît pas son périmètre : il reçoit la technique, sa sonde, un
nombre maximal de tours et un objectif mesurable. Tout le reste est refusé par
la politique de périmètre, qui s'applique avant l'exécution de chaque outil.

`executer` est le point d'entrée consommé par le moteur (lot 3).
"""

from piege.agents.attaquant.executant import executer, planifier_tours, transcription
from piege.agents.attaquant.outils import (Cible___deposit, Cible___mesure,
                                           Cible___sonde, OUTILS)
from piege.agents.attaquant.strands import (INVITE_ATTAQUANT, construire_agent,
                                            disponible, executer_strands,
                                            paquet_sortie)
from piege.agents.attaquant.variantes import (ENCODAGES, choisir_sonde, diluer,
                                              encoder, sonde_du_tour,
                                              transformation_pour, variantes)

__all__ = [
    "executer", "planifier_tours", "transcription", "variantes", "choisir_sonde",
    "sonde_du_tour", "encoder", "transformation_pour", "diluer", "ENCODAGES",
    "Cible___sonde", "Cible___deposit", "Cible___mesure", "OUTILS",
    "disponible", "construire_agent", "executer_strands", "paquet_sortie",
    "INVITE_ATTAQUANT",
]