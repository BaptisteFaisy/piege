"""Piège — politique de périmètre : ce qui est autorisé, évalué avant l'outil.

Référence locale de l'annexe B de la spécification : chaque outil passe par
cette évaluation **avant** son exécution. L'évaluation porte sur des faits
structurés, jamais sur du texte libre. Un agent attaquant qui tenterait
d'élargir son périmètre se heurte ici, et le refus est journalisé avec la
règle violée (c'est la preuve montrée à 1:45 dans la démonstration).
"""

from __future__ import annotations

from typing import Callable, Optional

from piege.erreurs import (ArretUrgence, AutorisationHumaineAbsente,
                           BudgetEpuise, ErreurPiege, HorsPerimetre,
                           MandatExpire, MandatInvalide, ProductionInterdite)
from piege.types import (Application, Campagne, Decision, Environnement,
                         Mandat, ProductionAutorisee, Technique, maintenant_utc)

__all__ = ["evaluer", "exiger", "lever_refus", "OUTIL_SONDE", "OUTIL_MESURE",
           "OUTIL_DEPOT", "OUTIL_GARDE_PROPOSE", "OUTIL_GARDE_APPLIQUE",
           "OUTIL_REJOUE", "REGLES"]

OUTIL_SONDE = "Cible___sonde"
OUTIL_MESURE = "Cible___mesure"
OUTIL_DEPOT = "F___deposer"
OUTIL_GARDE_PROPOSE = "Garde___propose"
OUTIL_GARDE_APPLIQUE = "Garde___applique"
OUTIL_REJOUE = "Cible___rejoue"

OUTILS_CIBLE = (OUTIL_SONDE, OUTIL_MESURE, OUTIL_REJOUE, OUTIL_DEPOT)
ROLES_AUTORISES_CORRECTIF = ("commanditaire", "analyste")
TYPES_CORRECTIF_APPLICABLES = ("garde_fou", "politique")

EXCEPTIONS = {
    "mandat_invalide": MandatInvalide,
    "mandat_expire": MandatExpire,
    "hors_perimetre": HorsPerimetre,
    "production_interdite": ProductionInterdite,
    "budget_epuise": BudgetEpuise,
    "arret_urgence": ArretUrgence,
    "autorisation_absente": AutorisationHumaineAbsente,
}


def refus(regle: str, code: str, motif: str, outil: str, faits: dict) -> Decision:
    """Construit une décision de refus (forme gelée par le contrat)."""
    return Decision(accorde=False, regle=regle, motif=motif, outil=outil,
                    faits=dict(faits), code=code)


def accord(outil: str, faits: dict) -> Decision:
    """Construit une décision d'autorisation."""
    return Decision(accorde=True, regle="autorise", motif="aucune règle violée",
                    outil=outil, faits=dict(faits), code="")


def _regle_mandat(outil, faits):
    """Mandat présent, valide, dans sa fenêtre (règles 1 et 2 de l'annexe B)."""
    statut = faits.get("mandat_statut")
    if statut != "valide":
        return refus("mandat.statut", "mandat_invalide",
                     "mandat absent ou non valide (statut %r)" % statut, outil, faits)
    debut, fin = faits.get("mandat_debut", ""), faits.get("mandat_fin", "")
    instant = faits.get("maintenant") or maintenant_utc()
    if debut and fin and not debut <= instant <= fin:
        return refus("mandat.fenetre", "mandat_expire",
                     "instant %s hors fenêtre [%s → %s]" % (instant, debut, fin),
                     outil, faits)
    return None


def _regle_perimetre(outil, faits):
    """Cible, technique et environnement couverts par le mandat."""
    if faits.get("cible_id") != faits.get("mandat_application_id"):
        return refus("perimetre.application", "hors_perimetre",
                     "cible %s hors du périmètre du mandat" % faits.get("cible_id"),
                     outil, faits)
    if faits.get("technique_id") not in (faits.get("mandat_techniques") or []):
        return refus("perimetre.technique", "hors_perimetre",
                     "technique %s hors du périmètre du mandat"
                     % faits.get("technique_id"), outil, faits)
    environnement = faits.get("cible_environnement")
    if environnement not in (faits.get("mandat_environnements") or []):
        return refus("perimetre.environnement", "hors_perimetre",
                     "environnement %s non couvert par le mandat" % environnement,
                     outil, faits)
    if environnement not in (faits.get("technique_environnement") or []):
        return refus("perimetre.technique.environnement", "hors_perimetre",
                     "la technique %s ne couvre pas l'environnement %s"
                     % (faits.get("technique_id"), environnement), outil, faits)
    return None


def _regle_production(outil, faits):
    """Production : interdite par le catalogue avant de l'être par le mandat."""
    if faits.get("cible_environnement") != Environnement.PROD.value:
        return None
    if faits.get("technique_production") == ProductionAutorisee.JAMAIS.value:
        return refus("production.catalogue", "production_interdite",
                     "la technique %s est interdite en production par le "
                     "catalogue : un mandat ne peut pas la lever"
                     % faits.get("technique_id"), outil, faits)
    if not faits.get("production_autorisee"):
        return refus("production.mandat", "production_interdite",
                     "production non autorisée par le mandat", outil, faits)
    return None


def _regle_budget(outil, faits):
    """Budget d'appels et de jetons : arrêt propre au seuil (ENF-02)."""
    appels = faits.get("campagne_appels_restants")
    if appels is not None and appels <= 0:
        return refus("budget.appels", "budget_epuise",
                     "budget d'appels épuisé", outil, faits)
    jetons = faits.get("campagne_jetons_restants")
    besoin = faits.get("technique_budget_jetons", 0)
    if jetons is not None and besoin and jetons < besoin:
        return refus("budget.jetons", "budget_epuise",
                     "budget de jetons insuffisant (%s < %s)" % (jetons, besoin),
                     outil, faits)
    return None


def _regle_arret(outil, faits):
    """Arrêt d'urgence : un geste, effet immédiat (ENF-14)."""
    if faits.get("arret_urgence"):
        return refus("arret.urgence", "arret_urgence",
                     "arrêt d'urgence actif", outil, faits)
    return None


def _regle_correctif(outil, faits):
    """Accord humain explicite et type de correctif applicable (EF-42)."""
    if outil != OUTIL_GARDE_APPLIQUE:
        return None
    if not faits.get("correctif_autorisation_humaine"):
        return refus("correctif.autorisation", "autorisation_absente",
                     "aucun accord humain explicite : application refusée",
                     outil, faits)
    if faits.get("correctif_autorise_par") not in ROLES_AUTORISES_CORRECTIF:
        return refus("correctif.role", "autorisation_absente",
                     "rôle %r non habilité à autoriser un correctif"
                     % faits.get("correctif_autorise_par"), outil, faits)
    if faits.get("correctif_type") not in TYPES_CORRECTIF_APPLICABLES:
        return refus("correctif.type", "autorisation_absente",
                     "le service n'applique que garde_fou et politique, pas %r"
                     % faits.get("correctif_type"), outil, faits)
    return None


def _regle_depot(outil, faits):
    """Famille F : dépôt sur l'index de test uniquement (EF-17)."""
    if outil != OUTIL_DEPOT:
        return None
    if faits.get("index_cible") == faits.get("index_de_test"):
        return None
    if faits.get("index_cible") == faits.get("index_production") \
            and faits.get("depot_production"):
        return None
    return refus("depot.index", "hors_perimetre",
                 "dépôt refusé : index cible hors index de test de la campagne",
                 outil, faits)


REGLES: tuple[Callable[[str, dict], Optional[Decision]], ...] = (
    _regle_mandat, _regle_perimetre, _regle_production, _regle_budget,
    _regle_arret, _regle_correctif, _regle_depot,
)


def evaluer(outil: str, faits: dict) -> Decision:
    """Évalue la politique pour un outil et un jeu de faits structurés.

    Les règles sont appliquées dans l'ordre normatif de l'annexe B ; la
    première règle violée gagne (le refus le plus fort est celui qui arrête
    l'exécution). Ne lève jamais : le refus est une `Decision`.
    """
    faits = dict(faits or {})
    for regle in REGLES:
        decision = regle(outil, faits)
        if decision is not None:
            return decision
    return accord(outil, faits)


def faits_pour(mandat: Mandat, technique: Technique, cible: Application,
               campagne: Campagne, arret_urgence: bool = False,
               appels_restants: Optional[int] = None,
               jetons_restants: Optional[int] = None,
               maintenant: Optional[str] = None) -> dict:
    """Construit le jeu de faits structuré depuis les enregistrements gelés."""
    return {
        "outil": OUTIL_SONDE,
        "mandat_statut": mandat.statut.value,
        "mandat_debut": mandat.fenetre_debut,
        "mandat_fin": mandat.fenetre_fin,
        "maintenant": maintenant or maintenant_utc(),
        "cible_id": cible.id,
        "mandat_application_id": mandat.application_id,
        "technique_id": technique.id,
        "mandat_techniques": list(mandat.perimetre_techniques),
        "technique_environnement": [e.value for e in technique.environnement],
        "cible_environnement": cible.environnement.value,
        "mandat_environnements": [e.value for e in mandat.environnements],
        "technique_production": technique.production.value,
        "production_autorisee": bool(mandat.production_autorisee),
        "campagne_appels_restants": appels_restants,
        "campagne_jetons_restants": jetons_restants,
        "technique_budget_jetons": 0,
        "arret_urgence": bool(arret_urgence),
        "tenant_id": mandat.tenant_id,
    }


def exiger(mandat: Mandat, technique: Technique, cible: Application,
           campagne: Campagne, arret_urgence: bool = False,
           appels_restants: Optional[int] = None,
           jetons_restants: Optional[int] = None,
           maintenant: Optional[str] = None) -> Decision:
    """Évalue la politique d'une sonde à partir des enregistrements du domaine."""
    faits = faits_pour(mandat, technique, cible, campagne, arret_urgence,
                        appels_restants, jetons_restants, maintenant)
    return evaluer(OUTIL_SONDE, faits)


def lever_refus(decision: Decision) -> None:
    """Transforme un refus en exception de domaine ; ne fait rien si autorisé."""
    if decision.accorde:
        return
    classe = EXCEPTIONS.get(decision.code, ErreurPiege)
    raise classe(decision.motif, code=decision.code,
                 details={"regle": decision.regle, "outil": decision.outil})
