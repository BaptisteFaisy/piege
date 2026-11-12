"""Piège — agent juge : verdict structuré, double passage, revue humaine.

Le juge décide si une tentative a réussi. Il ne fixe **jamais** la sévérité
(règle C5) : il classe un fait observable (`impact` de 1 à 4) que
`piege.severite` transforme ensuite en sévérité. Il n'a aucun outil et ne peut
pas interroger la cible (spécification §18.1).
"""

from piege.agents.juge.double_passage import (confronter, graine_secondaire,
                                              second_passage)
from piege.agents.juge.evaluation import (CIBLE_ACCORD, CIBLE_DETECTION,
                                          CIBLE_FAUX_POSITIFS, charger_cibles,
                                          mesurer_detection, mesurer_juge,
                                          rapport, technique_etalon)
from piege.agents.juge.juge import juger
from piege.agents.juge.local import juger_deterministe
from piege.agents.juge.prompts import VERSION_INVITE
from piege.agents.juge.revue import (SEUIL_DEFAUT, revue_humaine_requise,
                                     seuil_confiance, trancher)
from piege.agents.juge.schema import SCHEMA, valider_sortie

__all__ = [
    "juger", "juger_deterministe", "second_passage", "confronter",
    "graine_secondaire", "revue_humaine_requise", "seuil_confiance", "trancher",
    "SEUIL_DEFAUT", "SCHEMA", "valider_sortie", "VERSION_INVITE",
    "charger_cibles", "mesurer_juge", "mesurer_detection", "rapport",
    "technique_etalon", "CIBLE_ACCORD", "CIBLE_DETECTION", "CIBLE_FAUX_POSITIFS",
]
