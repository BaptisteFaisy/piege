"""Piège — budget restant et écarts de coût (KPI-7, ENF-10, recette R17).

Le budget restant est exposé au portail et à l'API : le responsable de compte
voit la consommation réelle, pas une estimation. L'écart avec la projection de
l'annexe F déclenche la revue R17 au-delà de 25 %.
"""

from __future__ import annotations

from typing import Optional

from piege.observabilite.compteurs import Compteur
from piege.types import Campagne, Mandat

__all__ = ["budget_restant", "PROJECTION_ANNEXE_F", "ecart_projection",
           "SEUIL_REVUE"]

# Projection de l'annexe F.5 : coût d'inférence par campagne complète, en $.
PROJECTION_ANNEXE_F = {"mixte": 3.35, "nova_lite": 0.17, "modele_fort": 8.91}
SEUIL_REVUE = 0.25


def budget_restant(campagne: Campagne, compteur: Optional[Compteur] = None,
                   mandat: Optional[Mandat] = None) -> dict:
    """État du budget d'une campagne, pour le portail et l'API.

    Les plafonds viennent du mandat quand il est fourni ; la consommation vient
    du compteur mesuré (ou des compteurs portés par la campagne).
    """
    consommes = compteur.vers_dict() if compteur is not None else {
        "appels": campagne.appels, "jetons": campagne.jetons,
        "cout": campagne.cout_mesure}
    appels_max = mandat.budget_appels if mandat else 0
    jetons_max = mandat.budget_jetons if mandat else 0
    appels = int(consommes.get("appels", 0))
    jetons = int(consommes.get("jetons", 0))
    return {
        "campagne_id": campagne.id,
        "appels_consommes": appels,
        "appels_restants": (appels_max - appels) if appels_max else None,
        "jetons_consommes": jetons,
        "jetons_restants": (jetons_max - jetons) if jetons_max else None,
        "part_appels": round(appels / appels_max, 4) if appels_max else None,
        "part_jetons": round(jetons / jetons_max, 4) if jetons_max else None,
        "cout_mesure": float(consommes.get("cout", 0.0)),
    }


def ecart_projection(cout_mesure: float, strategie: str = "mixte") -> dict:
    """Écart entre le coût mesuré et la projection de l'annexe F (R17)."""
    if strategie not in PROJECTION_ANNEXE_F:
        raise ValueError("stratégie inconnue : %r (attendu %s)"
                         % (strategie, sorted(PROJECTION_ANNEXE_F)))
    projection = PROJECTION_ANNEXE_F[strategie]
    ecart = cout_mesure - projection
    relatif = abs(ecart) / projection if projection else 0.0
    return {
        "strategie": strategie,
        "cout_mesure": round(cout_mesure, 4),
        "projection": projection,
        "ecart": round(ecart, 4),
        "ecart_relatif": round(relatif, 4),
        "depassement_25_pourcent": relatif > SEUIL_REVUE,
        "revue_requise": relatif > SEUIL_REVUE,
    }
