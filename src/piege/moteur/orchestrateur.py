"""Piège — orchestrateur de campagne.

Ordre imposé par la spécification : **la politique est évaluée avant chaque
sonde** (§17.3), le budget est plafonné dans le code (ENF-02), l'arrêt
d'urgence est testé entre chaque échange (ENF-14), et chaque échange est
journalisé (ENF-04). Le verdict vient du juge, jamais de l'attaquant, et la
sévérité n'est jamais calculée ici (règle C5).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Optional

from piege.moteur import arret as arret_module
from piege.moteur import resolution
from piege.moteur.budget import CompteurBudget
from piege.moteur.configuration import (ConfigurationCampagne,
                                        ConfigurationTechnique)
from piege.moteur.graine import graine_technique
from piege.types import (Campagne, Execution, StatutCampagne, Technique,
                         maintenant_utc)

__all__ = ["Contexte", "preparer", "executer_campagne", "executer_technique"]


@dataclass
class Contexte:
    """Tout l'état résolu d'une campagne, préparé avant la première sonde."""

    config: ConfigurationCampagne
    mandat: Any
    application: Any
    cible: Any
    techniques: list
    fournisseur: Any
    fournisseur_juge: Any
    journal: Any
    entrepot: Any
    budget: CompteurBudget
    arret: arret_module.ArretUrgence
    attaquant: Any
    juge: Optional[Any]
    evaluateur: Any
    campagne: Campagne


def preparer(config: ConfigurationCampagne, maintenant: Optional[str] = None) -> Contexte:
    """Résout mandat, cible, techniques, budget et composants (EF-04, EF-10)."""
    config.valider()
    entrepot = resolution.resoudre_entrepot(config)
    mandat = resolution.resoudre_mandat(config, entrepot, maintenant)
    application = resolution.resoudre_application(config, entrepot, mandat)
    cible = resolution.resoudre_cible(config, application)
    techniques = resolution.resoudre_techniques(config)
    campagne = _campagne(config, mandat, techniques)
    budget = CompteurBudget(config.budget_appels_effectif(mandat),
                            config.budget_jetons_effectif(mandat))
    arret = arret_module.arret_de(campagne.id)
    if config.arrete_urgence:
        arret.declencher("arret demande avant lancement")
    return Contexte(
        config=config, mandat=mandat, application=application, cible=cible,
        techniques=techniques,
        fournisseur=resolution.resoudre_fournisseur(config),
        fournisseur_juge=resolution.resoudre_fournisseur(config, juge=True),
        journal=resolution.resoudre_journal(config, entrepot), entrepot=entrepot,
        budget=budget, arret=arret,
        attaquant=resolution.resoudre_attaquant(config),
        juge=resolution.resoudre_juge(config),
        evaluateur=resolution.resoudre_evaluateur(config), campagne=campagne)


def _campagne(config: ConfigurationCampagne, mandat: Any,
              techniques: list) -> Campagne:
    """Enregistrement de campagne : fourni, ou construit à la volée."""
    if config.campagne is not None:
        return config.campagne
    identifiant = config.campagne_id or "CMP-%04d" % (config.graine % 10000)
    return Campagne(
        id=identifiant, mandat_id=mandat.id, application_id=mandat.application_id,
        tenant_id=mandat.tenant_id, type=config.type, graine=config.graine,
        statut=StatutCampagne.PLANIFIEE,
        techniques_prevues=[t.id for t in techniques])


def executer_campagne(config: ConfigurationCampagne) -> Campagne:
    """Exécute une campagne complète et rend son enregistrement à jour."""
    contexte = preparer(config)
    contexte.campagne.statut = StatutCampagne.EN_COURS
    contexte.campagne.debutee_le = maintenant_utc()
    executions = _executer_toutes(contexte)
    _finaliser(contexte, executions)
    return contexte.campagne


def _executer_toutes(contexte: Contexte) -> list[Execution]:
    """Exécute les techniques en parallélisme borné, arrêt propre au seuil."""
    parallelisme = max(1, min(contexte.config.parallelisme, len(contexte.techniques)))
    if parallelisme == 1:
        return [_une_technique(contexte, t) for t in contexte.techniques]
    with ThreadPoolExecutor(max_workers=parallelisme) as pool:
        return list(pool.map(lambda t: _une_technique(contexte, t),
                             contexte.techniques))


def _une_technique(contexte: Contexte, technique: Technique) -> Execution:
    """Périmètre → budget → attaque → jugement, dans cet ordre."""
    if contexte.arret.actif:
        return _refus(contexte, technique, "arret_urgence", "arret.urgence",
                      "arrêt d'urgence actif")
    decision = contexte.evaluateur(
        mandat=contexte.mandat, technique=technique, cible=contexte.application,
        campagne=contexte.campagne, arret_urgence=contexte.arret.actif,
        appels_restants=contexte.budget.appels_restants(),
        jetons_restants=contexte.budget.jetons_restants(),
        maintenant=maintenant_utc())
    if not decision.accorde:
        return _refus(contexte, technique, decision.code, decision.regle,
                      decision.motif)
    return _attaquer_et_juger(contexte, technique)


def _refus(contexte: Contexte, technique: Technique, code: str, regle: str,
           motif: str) -> Execution:
    """Exécution refusée : aucune sonde envoyée, refus journalisé (R1, R4)."""
    execution = _execution_vide(contexte, technique, statut="refuse", erreur=code)
    execution.motif = motif
    contexte.journal.consigner("moteur", "refus", contexte.mandat.tenant_id,
                               {"technique": technique.id, "regle": regle,
                                "code": code, "motif": motif})
    return _enregistrer(contexte, execution)


def _execution_vide(contexte: Contexte, technique: Technique, statut: str,
                    erreur: str) -> Execution:
    """Exécution sans échange, pour les refus et les interruptions."""
    return Execution(
        id="EXE-%s-%s-000" % (contexte.campagne.id, technique.id),
        campagne_id=contexte.campagne.id, technique_id=technique.id,
        application_id=contexte.mandat.application_id,
        tenant_id=contexte.mandat.tenant_id, statut=statut,
        sondes_envoyees=[], reponse_brute="", jetons=0, latence_ms=0,
        verdict=None, impact=None, confiance=0.0, citation="", motif="",
        garde_fou_declenche=False, revue_humaine=False,
        graine=graine_technique(contexte.config.graine, technique.id),
        tours=0, modele="", erreur=erreur)


def _attaquer_et_juger(contexte: Contexte, technique: Technique) -> Execution:
    """Attaque bornée puis jugement ; le budget et l'arrêt sont transmis."""
    execution = contexte.attaquant(
        technique, contexte.cible, contexte.mandat, contexte.campagne,
        contexte.fournisseur, graine_technique(contexte.config.graine, technique.id),
        contexte.journal, budget=contexte.budget, arret=contexte.arret)
    _juger(contexte, technique, execution)
    return _enregistrer(contexte, execution)


def _juger(contexte: Contexte, technique: Technique, execution: Execution) -> None:
    """Pose le verdict (et la revue humaine) sur une exécution attaquée.

    Un juge défaillant ne fait **pas** perdre la campagne : l'exécution est
    conservée, marquée non statuée et envoyée en revue humaine. Perdre trente
    sondes parce qu'un appel de modèle a rendu une sortie illisible serait
    exactement l'inverse du service promis.
    """
    if execution.erreur or not execution.sondes_envoyees:
        return
    from piege.erreurs import FournisseurIndisponible

    try:
        verdict = _verdict(contexte, technique, execution)
    except FournisseurIndisponible as erreur:
        _jugement_indisponible(contexte, technique, execution, erreur)
        return
    execution.verdict = verdict.verdict
    execution.impact = verdict.impact
    execution.confiance = verdict.confiance
    execution.citation = verdict.citation
    execution.motif = verdict.motif
    execution.garde_fou_declenche = verdict.garde_fou_declenche
    execution.revue_humaine = bool(verdict.revue_humaine
                                   or _revue_requise(verdict))
    contexte.journal.consigner("juge", "verdict", contexte.mandat.tenant_id,
                               {"technique": technique.id,
                                "verdict": getattr(verdict.verdict, "value",
                                                   verdict.verdict),
                                "impact": verdict.impact,
                                "confiance": verdict.confiance})


def _jugement_indisponible(contexte: Contexte, technique: Technique,
                           execution: Execution, erreur: Exception) -> None:
    """Verdict illisible : exécution conservée, non statuée, en revue humaine.

    Le motif visible est court ; le journal, lui, reçoit le diagnostic complet
    (extrait brut, clés reçues) : un humain doit pouvoir trancher sans rejouer
    l'appel, et l'incident doit rester explicable a posteriori.
    """
    execution.verdict = None
    execution.impact = None
    execution.confiance = 0.0
    execution.citation = ""
    execution.revue_humaine = True
    execution.statut = "verdict_indisponible"
    execution.motif = "verdict illisible : %s" % str(erreur)[:160]
    contexte.journal.consigner("juge", "verdict_indisponible",
                               contexte.mandat.tenant_id,
                               dict(technique=technique.id,
                                    execution=execution.id,
                                    motif=execution.motif,
                                    **_diagnostic(erreur)))


def _diagnostic(erreur: Exception) -> dict:
    """Détails d'une erreur de juge dignes du journal (rien d'inventé)."""
    details = getattr(erreur, "details", None) or {}
    return {cle: details[cle] for cle in ("regle", "extrait", "longueur", "cles")
            if details.get(cle) not in (None, "", [])}


def _revue_requise(verdict) -> bool:
    """Critères de revue humaine du lot 5 ; `False` s'il n'est pas mergé."""
    try:
        from piege.agents.juge.revue import revue_humaine_requise
    except ImportError:
        return False
    return revue_humaine_requise(verdict)


def _verdict(contexte: Contexte, technique: Technique, execution: Execution):
    """Appelle le juge, avec double passage sauf injection d'un juge tiers."""
    if contexte.juge is None:
        from piege.agents.juge.local import juger_deterministe

        return juger_deterministe(technique, execution.reponse_brute,
                                  execution.graine)
    verdict = contexte.juge(technique, execution.reponse_brute,
                            contexte.fournisseur_juge, execution.graine)
    if not _double_passage_actif(contexte):
        return verdict
    from piege.agents.juge import second_passage

    return second_passage(verdict, technique, execution.reponse_brute,
                          contexte.fournisseur_juge)


def _double_passage_actif(contexte: Contexte) -> bool:
    """Double passage : auto avec le juge du lot 5, jamais sur un juge injecté."""
    if contexte.config.double_passage is not None:
        return bool(contexte.config.double_passage)
    return contexte.config.juge is None


def _enregistrer(contexte: Contexte, execution: Execution) -> Execution:
    """Persiste l'exécution (si un entrepôt est disponible) et la retourne."""
    if contexte.entrepot is not None:
        try:
            contexte.entrepot.ecrire("executions", execution.vers_dict())
        except Exception:                                 # noqa: BLE001
            pass
    return execution


def _finaliser(contexte: Contexte, executions: list[Execution]) -> None:
    """Statut final, compteurs et journal de fin de campagne."""
    contexte.campagne.appels = contexte.budget.appels_consommes
    contexte.campagne.jetons = contexte.budget.jetons_consommes
    # Coût réel, sommé depuis ce que le routeur a facturé pour chaque appel
    # (ENF-10, KPI-7) : jamais une estimation a posteriori.
    contexte.campagne.cout_mesure = round(
        sum(float(getattr(e, "cout", 0.0) or 0.0) for e in executions), 6)
    contexte.campagne.techniques_executes = [
        e.technique_id for e in executions if e.statut == "execute"]
    contexte.campagne.statut = _statut_final(contexte, executions)
    contexte.campagne.terminee_le = maintenant_utc()
    contexte.journal.consigner("moteur", "campagne_terminee",
                               contexte.mandat.tenant_id,
                               {"campagne": contexte.campagne.id,
                                "statut": contexte.campagne.statut.value,
                                "appels": contexte.campagne.appels,
                                "jetons": contexte.campagne.jetons})
    if contexte.entrepot is not None:
        contexte.entrepot.ecrire("campagnes", contexte.campagne.vers_dict())


def _statut_final(contexte: Contexte, executions: list[Execution]) -> StatutCampagne:
    """Interrompue sur budget épuisé, suspendue sur arrêt, terminée sinon."""
    if any(e.erreur == "budget_epuise" for e in executions) or contexte.budget.epuise():
        return StatutCampagne.INTERROMPUE
    if contexte.arret.actif:
        return StatutCampagne.SUSPENDUE
    return StatutCampagne.TERMINEE


def executer_technique(config: ConfigurationTechnique) -> Execution:
    """Rejoue une technique précise depuis un finding (EF-54, R19)."""
    campagne_config = ConfigurationCampagne(
        mandat=config.mandat, application=None, cible=config.cible,
        techniques=[config.technique], graine=config.graine, parallelisme=1,
        fournisseur=config.fournisseur, fournisseur_juge=config.fournisseur_juge,
        attaquant=config.attaquant, juge=config.juge,
        evaluateur=config.evaluateur, entrepot=config.entrepot,
        journal=config.journal, campagne=config.campagne,
        cible_spec={}, tenant_id=config.mandat.tenant_id)
    contexte = preparer(campagne_config)
    return _une_technique(contexte, config.technique)
