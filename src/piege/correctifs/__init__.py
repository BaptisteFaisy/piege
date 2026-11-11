"""Piège — correctifs : proposition, accord humain, application, rejeu, contrôles.

Une découverte sans correctif vérifié est une information, pas un service. Ce
paquet ferme la boucle : proposition classée par effort et réduction de risque,
accord humain explicite, application limitée aux garde-fous et aux politiques,
rejeu de l'attaque d'origine, preuve de fermeture datée, contrôle de régression
et contrôle d'effet de bord sur les faux refus.
"""

from piege.correctifs.application import (appliquer, annuler, est_applique,
                                          theme_du_correctif)
from piege.correctifs.autorisation import (autoriser, est_autorise, exiger_autorisation,
                                           refuser)
from piege.correctifs.boucle import (BilanCorrection, boucle_complete,
                                     choisir_correctif)
from piege.correctifs.controles import (controler_effet_de_bord,
                                        controler_regression,
                                        fermeture_complete,
                                        phrase_effet_de_bord)
from piege.correctifs.proposition import (contenu_correctif, effort_et_reduction,
                                          proposer, type_correctif)
from piege.correctifs.rejeu import (chemin_preuve, est_ferme, fermer, rejouer)

__all__ = [
    "proposer", "type_correctif", "effort_et_reduction", "contenu_correctif",
    "autoriser", "refuser", "est_autorise", "exiger_autorisation", "appliquer",
    "annuler", "est_applique", "theme_du_correctif", "rejouer", "est_ferme",
    "fermer", "chemin_preuve", "controler_regression",
    "controler_effet_de_bord", "phrase_effet_de_bord", "fermeture_complete",
    "BilanCorrection", "boucle_complete", "choisir_correctif",
]
