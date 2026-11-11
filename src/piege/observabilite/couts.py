"""Piège — table de tarifs et coût **mesuré** par campagne.

Un seul endroit définit les prix (CONTRACTS.md §8) : les modifier ailleurs est
une erreur. Le coût est calculé depuis les jetons réellement consommés, jamais
estimé a posteriori (ENF-10). Un modèle inconnu est refusé : un tarif deviné
produirait une facture fausse, ce qui est exactement ce que le service promet
d'éviter.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege.erreurs import ValeurHorsPlage
from piege.observabilite.compteurs import Compteur

__all__ = ["TARIFS", "cout", "cout_mesure", "cout_par_tenant", "cout_par_modele",
           "MODELE_ATTAQUANT", "MODELE_JUGE", "MODELE_REPLI"]

# Dollars par million de jetons (spécification §23.2, à confirmer en S1).
TARIFS = {
    "nova-lite": {"entree": 0.06, "sortie": 0.24},
    "modele-fort": {"entree": 3.00, "sortie": 15.00},
    "inferhub-flash": {"entree": 0.00075, "sortie": 0.00375},
}

# Rôles : l'attaquant n'a pas besoin d'un modèle fort, le juge si (§23.3).
MODELE_ATTAQUANT = "nova-lite"
MODELE_JUGE = "modele-fort"
MODELE_REPLI = "inferhub-flash"

# Modèles de simulation hors ligne : tarifs alignés sur le rôle qu'ils jouent.
ALIASES = {"local-deterministe": MODELE_ATTAQUANT, "double": MODELE_ATTAQUANT,
           "simule-local": MODELE_ATTAQUANT}

PAR_MILLION = 1_000_000.0


def tarif(modele: str) -> dict:
    """Tarif d'un modèle ; refuse un modèle inconnu (jamais de tarif deviné)."""
    cle = ALIASES.get(modele, modele)
    if cle not in TARIFS:
        raise ValeurHorsPlage(
            "modèle %r absent de la table de tarifs (%s)"
            % (modele, ", ".join(sorted(TARIFS))),
            code="valeur_hors_plage", details={"regle": "cout.tarif"})
    return TARIFS[cle]


def cout(modele: str, jetons_entree: int, jetons_sortie: int) -> float:
    """Coût en dollars d'un échange, arrondi au centième de centime."""
    if jetons_entree < 0 or jetons_sortie < 0:
        raise ValeurHorsPlage("jetons négatifs", code="valeur_hors_plage",
                              details={"regle": "cout.jetons"})
    prix = tarif(modele)
    valeur = (jetons_entree / PAR_MILLION * prix["entree"]
              + jetons_sortie / PAR_MILLION * prix["sortie"])
    return round(valeur, 6)


def cout_mesure(executions: Iterable[object], modele: Optional[str] = None,
                modele_juge: str = MODELE_JUGE) -> float:
    """Coût mesuré d'une campagne à partir de ses exécutions.

    Chaque exécution porte ses jetons et le modèle qui les a consommés ; le
    juge est facturé à part quand l'exécution le déclare. Sans modèle déclaré,
    le modèle d'attaque par défaut s'applique.
    """
    total = 0.0
    for execution in executions:
        donnees = execution if isinstance(execution, dict) else execution.__dict__
        jetons = int(donnees.get("jetons", 0) or 0)
        nom = donnees.get("modele") or modele or MODELE_ATTAQUANT
        total += cout(nom, jetons, 0)
        if donnees.get("verdict") is not None:
            total += cout(modele_juge, 1500, 200)
    return round(total, 6)


def cout_par_modele(compteur: Compteur) -> dict:
    """Répartition du coût par modèle, pour le rapport dirigeant."""
    return {modele: dict(part) for modele, part in compteur.par_modele.items()}


def cout_par_tenant(compteurs: dict) -> dict:
    """Coût cumulé par tenant, exposé au responsable de compte (EF-63)."""
    return {tenant: round(compteur.cout, 6) for tenant, compteur in compteurs.items()}
