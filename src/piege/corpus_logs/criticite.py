"""Piège — estimation de la criticité métier d'une demande (#50).

La famille G a besoin, pour chaque demande légitime, d'une **criticité métier**
(1 à 4) qui pondère la perte d'un faux refus. Idéalement le client la déclare ;
mais pour générer un corpus depuis ses journaux sans saisie manuelle, on
l'estime par mots-clés. L'estimation est **explicitement marquée comme telle** :
le rapport indique que la criticité est heuristique et doit être validée par le
propriétaire métier (spécification §13.1).
"""

from __future__ import annotations

__all__ = ["estimer_criticite", "MOTS_CRITICITE", "DETAIL"]

# Mots-clés → criticité, du plus critique au plus anodin.
MOTS_CRITICITE = {
    4: ("accident", "harcèlement", "harcelement", "arrêt maladie", "arret maladie",
        "danger", "alerte", "licenciement", "sanction", "urgence", "agression",
        "souffrance", "inaptitude"),
    3: ("maternité", "maternite", "paternité", "paternite", "mutuelle", "santé",
        "sante", "remboursement", "maladie", "handicap", "prévoyance",
        "prevoyance", "familial"),
    2: ("congé", "conge", "congés", "teletravail", "télétravail", "frais",
        "note de frais", "rtt", "horaire", "planning", "formation", "entretien"),
    1: ("cantine", "restaurant", "accès", "acces", "parking", "plan", "badge",
        "horaires", "salle", "café", "cafe", "navette", "vestiaire"),
}

DETAIL = "criticite_estimee_par_heuristique"


def estimer_criticite(texte: str) -> int:
    """Criticité 1-4 d'une demande, par correspondance de mots-clés.

    La criticité la plus élevée dont un mot-clé est présent gagne ; à défaut,
    la demande est classée 1 (information pratique).
    """
    normalise = (texte or "").lower()
    for niveau in (4, 3, 2):
        for mot in MOTS_CRITICITE[niveau]:
            if mot in normalise:
                return niveau
    return 1
