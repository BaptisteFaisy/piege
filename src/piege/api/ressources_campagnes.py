"""Piège — routes de campagne : lancement, progression, suspension, revue.

Le lancement est **synchrone** en mode démonstration : une campagne complète
dure quelques secondes hors ligne, ce qui rend le portail vivant sans introduire
de file d'attente. En déploiement réel, la route délègue à Step Functions et
rend la main immédiatement (lot 14) ; le contrat de réponse est identique.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.api.aides import (ecrire, exiger_role, introuvable, lire,
                            lire_ou_erreur)
from piege.moteur import ConfigurationCampagne, executer_campagne
from piege.moteur.arret import reprendre, suspendre
from piege.observabilite import budget_restant, compte
from piege.rapport.synthese import synthetiser_findings
from piege.types import (Application, Campagne, Execution, Famille, Mandat,
                         StatutCampagne, TypeCampagne, VerdictValeur,
                         depuis_dict, maintenant_utc)

__all__ = ["ROUTES", "lancer_campagne", "lire_campagne", "lister_executions",
           "suspendre_campagne", "reprendre_campagne", "trancher_execution"]


def _catalogue(api: Any) -> dict:
    """Catalogue chargé une fois par contexte d'API."""
    if api.catalogue is None:
        try:
            from piege.catalogue import charger_catalogue

            api.catalogue = charger_catalogue(api.dossier_catalogue)
        except Exception:                                     # noqa: BLE001
            api.catalogue = {}
    return api.catalogue


def lancer_campagne(api: Any, tenant: str, roles: list, corps: dict, **_) -> dict:
    """Lance une campagne (EF-10, EF-11) et synthétise ses découvertes."""
    exiger_role(roles, ["analyste", "commanditaire"], "lancer une campagne")
    mandat = _mandat(api, tenant, str(corps.get("mandat_id", "")))
    application = _application(api, tenant, mandat.application_id)
    config = _configuration(api, tenant, corps, mandat, application)
    _plafonner_techniques(config)
    campagne = executer_campagne(config)
    ecrire(api, "campagnes", campagne.vers_dict())
    executions = [depuis_dict(Execution, e)
                  for e in api.entrepot.lister("executions", tenant_id=tenant,
                                               campagne_id=campagne.id)]
    findings = synthetiser_findings(campagne, executions, application,
                                    _catalogue(api), api.entrepot)
    return {"campagne": campagne.vers_dict(),
            "executions": len(executions), "findings": len(findings),
            "budget": budget_restant(campagne, mandat=mandat)}


def _plafonner_techniques(config) -> None:
    """Plafond de techniques par campagne (garde-fou de l'instance publique).

    En mode « vrai modèle », chaque technique coûte un appel de modèle (cible)
    et un verdict (juge) : une campagne complète de 60 techniques prendrait
    plusieurs minutes sur une instance publique partagée. `PIEGE_MAX_TECHNIQUES`
    borne la demande et le dit explicitement, sans jamais tronquer en silence.
    """
    import os

    from piege.erreurs import ErreurPiege
    from piege.moteur.resolution import resoudre_techniques

    brut = os.environ.get("PIEGE_MAX_TECHNIQUES", "")
    if not brut:
        return
    plafond = int(brut)
    techniques = resoudre_techniques(config)
    if len(techniques) > plafond:
        raise ErreurPiege(
            "instance publique : %d techniques demandées, plafond de %d. "
            "Réduire le périmètre du mandat ou la liste de techniques."
            % (len(techniques), plafond),
            code="plafond_techniques",
            details={"regle": "api.plafond", "demandees": len(techniques),
                     "plafond": plafond})


def _mandat(api: Any, tenant: str, mandat_id: str) -> Mandat:
    from piege.securite import mandats as mandats_module

    brut = lire_ou_erreur(api, "mandats", mandat_id, tenant)
    return mandats_module.valider(depuis_dict(Mandat, brut))


def _application(api: Any, tenant: str, application_id: str) -> Application:
    brut = lire(api, "applications", application_id, tenant)
    if brut:
        return depuis_dict(Application, brut)
    return Application(id=application_id, tenant_id=tenant, nom=application_id,
                       type="rag", acces="", modele="",
                       environnement="test", exposition=2)


def _configuration(api: Any, tenant: str, corps: dict, mandat: Mandat,
                   application: Application) -> ConfigurationCampagne:
    """Construit la configuration de campagne depuis la requête."""
    familles = [Famille(f) for f in (corps.get("familles") or [])]
    technique_ids = corps.get("technique_ids") or None
    if not technique_ids and not familles:
        technique_ids = _techniques_applicables(api, application, mandat, corps)
    return ConfigurationCampagne(
        mandat=mandat, application=application, mandat_id=mandat.id,
        application_id=application.id, tenant_id=tenant,
        type=TypeCampagne(str(corps.get("type", "complete"))),
        graine=int(corps.get("graine", 0)),
        technique_ids=technique_ids,
        familles=familles or None,
        parallelisme=int(corps.get("parallelisme", 4)),
        cible_spec=dict(corps.get("cible_spec") or {}),
        cible=api.cible(application.id, dict(corps.get("cible_spec") or {})),
        catalogue=_catalogue(api),
        fournisseur=api.fournisseur, juge=api.juge, entrepot=api.entrepot,
        corpus_legitime_id=str(corps.get("corpus_legitime_id", "")))


def _techniques_applicables(api: Any, application: Application, mandat: Mandat,
                            corps: dict) -> Optional[list]:
    """Périmètre réellement exécutable (EF-02), au lieu de tout le catalogue.

    Sans ce filtre la campagne « tentait » les 60 techniques pour en voir 58
    refusées par la politique : autant d'exécutions vides, et un plafond de
    techniques dépourvu de sens en mode réel. Une technique demandée
    explicitement hors périmètre reste refusée par la politique (R4).
    """
    from piege.catalogue import techniques_applicables

    catalogue = _catalogue(api)
    if not catalogue:
        return None
    applicables = techniques_applicables(
        application, mandat, catalogue,
        corpus_legitime=bool(corps.get("corpus_legitime_id")))
    return [technique.id for technique in applicables] or None


def lire_campagne(api: Any, tenant: str, roles: list, id: str, **_) -> dict:
    """Progression en direct : exécutions, découvertes, budget restant."""
    del roles
    brut = lire_ou_erreur(api, "campagnes", id, tenant)
    campagne = depuis_dict(Campagne, brut)
    executions = api.entrepot.lister("executions", tenant_id=tenant, campagne_id=id)
    findings = api.entrepot.lister("findings", tenant_id=tenant, campagne_id=id)
    mandat = lire(api, "mandats", campagne.mandat_id, tenant)
    return {"campagne": brut,
            "progression": {"executions": len(executions),
                            "prevues": len(brut.get("techniques_prevues", [])),
                            "reussies": _compte_reussites(executions),
                            "refusees": _compte_refus(executions),
                            "en_revue": _compte_revue(executions)},
            "findings": len(findings),
            "budget": budget_restant(campagne, compte(id),
                                     depuis_dict(Mandat, mandat) if mandat else None)}


def _compte_reussites(executions: list[dict]) -> int:
    return len([e for e in executions if e.get("verdict") == "reussi"])


def _compte_refus(executions: list[dict]) -> int:
    return len([e for e in executions if e.get("statut") == "refuse"])


def _compte_revue(executions: list[dict]) -> int:
    return len([e for e in executions if e.get("revue_humaine")])


def lister_executions(api: Any, tenant: str, roles: list, id: str, **_) -> list:
    """Détail par technique d'une campagne (EF-14, EF-54)."""
    del roles
    lire_ou_erreur(api, "campagnes", id, tenant)
    return api.entrepot.lister("executions", tenant_id=tenant, campagne_id=id)


def suspendre_campagne(api: Any, tenant: str, roles: list, id: str,
                       corps: dict, **_) -> dict:
    """Arrêt immédiat en un geste (ENF-14, EF-15)."""
    exiger_role(roles, ["analyste", "commanditaire"], "suspendre une campagne")
    lire_ou_erreur(api, "campagnes", id, tenant)
    suspendre(id, str((corps or {}).get("motif", "suspension depuis le portail")))
    return {"campagne": id, "statut": StatutCampagne.SUSPENDUE.value,
            "arret": True, "date": maintenant_utc()}


def reprendre_campagne(api: Any, tenant: str, roles: list, id: str, **_) -> dict:
    """Reprise d'une campagne suspendue, état conservé."""
    exiger_role(roles, ["analyste", "commanditaire"], "reprendre une campagne")
    lire_ou_erreur(api, "campagnes", id, tenant)
    reprendre(id)
    return {"campagne": id, "arret": False, "date": maintenant_utc()}


def trancher_execution(api: Any, tenant: str, roles: list, id: str,
                       corps: dict, **_) -> dict:
    """Tranche un verdict ambigu en revue humaine (EF-22)."""
    from piege.erreurs import ValeurHorsPlage

    exiger_role(roles, ["analyste", "commanditaire"], "trancher un verdict")
    execution = lire_ou_erreur(api, "executions", id, tenant)
    decision = str((corps or {}).get("decision", ""))
    if decision not in ("confirme", "infirme", "classe_sans_suite"):
        raise ValeurHorsPlage("décision %r hors catalogue" % decision,
                              code="valeur_hors_plage",
                              details={"regle": "api.revue"})
    execution["revue_humaine"] = False
    if decision == "infirme":
        execution["verdict"] = VerdictValeur.ECHOUE.value
        execution["impact"] = None
    elif decision == "classe_sans_suite":
        execution["verdict"] = VerdictValeur.AMBIGU.value
    execution["motif"] = "%s | tranche_par=%s le %s" % (
        execution.get("motif", ""), roles[0] if roles else "analyste",
        maintenant_utc())
    ecrire(api, "executions", execution)
    api.entrepot.ecrire_journal({"qui": "api", "quoi": "revue_humaine",
                                 "tenant": tenant,
                                 "details": {"execution": id,
                                             "decision": decision},
                                 "marqueur": "trafic_reel"})
    return execution


ROUTES = [
    ("POST", "/campagnes", lancer_campagne),
    ("GET", "/campagnes/{id}", lire_campagne),
    ("POST", "/campagnes/{id}/suspendre", suspendre_campagne),
    ("POST", "/campagnes/{id}/reprendre", reprendre_campagne),
    ("GET", "/campagnes/{id}/executions", lister_executions),
    ("POST", "/executions/{id}/revue", trancher_execution),
]
