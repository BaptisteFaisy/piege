"""Piège — rejeu de l'attaque d'origine et preuve de fermeture (EF-43).

Une découverte n'est fermée que si l'attaque d'origine, rejouée après le
correctif, échoue. La preuve est datée, empreinte, et conservée de façon
immuable : c'est elle qui est produite dans l'attestation destinée à un tiers.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from piege.moteur.configuration import ConfigurationTechnique
from piege.moteur.orchestrateur import executer_technique
from piege.types import (Campagne, Correctif, Execution, Finding, Preuve,
                         StatutCampagne, StatutCorrectif, StatutFinding,
                         TypeCampagne, Technique, VerdictValeur, canonical,
                         empreinte, maintenant_utc)

__all__ = ["rejouer", "est_ferme", "fermer", "chemin_preuve"]

DOSSIER_PREUVES = "preuves-locales"


def chemin_preuve(campagne_id: str, technique_id: str,
                  dossier: str = DOSSIER_PREUVES) -> str:
    """Chemin de la preuve de rejeu (S3 en production, disque en local)."""
    return os.path.join(dossier, campagne_id, "%s-rejeu.json" % technique_id)


def rejouer(finding: Finding, cible: Any, mandat: Any, graine: int,
            technique: Optional[Technique] = None,
            catalogue: Optional[dict] = None, campagne: Optional[Campagne] = None,
            fournisseur: Any = None, juge: Optional[Any] = None,
            journal: Optional[Any] = None, entrepot: Optional[Any] = None,
            dossier_preuves: str = DOSSIER_PREUVES) -> tuple[Execution, Preuve]:
    """Rejoue la technique d'origine et rend (exécution, preuve datée)."""
    cible_technique = technique or _resoudre(finding, catalogue)
    campagne_rejeu = campagne or _campagne_rejeu(finding, mandat, graine)
    execution = executer_technique(ConfigurationTechnique(
        technique=cible_technique, mandat=mandat, cible=cible,
        campagne=campagne_rejeu, graine=graine, fournisseur=fournisseur,
        juge=juge, entrepot=entrepot, journal=journal))
    preuve = _preuve(execution, finding, campagne_rejeu, dossier_preuves)
    if journal is not None:
        journal.consigner("correctifs", "rejeu", finding.tenant_id,
                          {"finding": finding.id,
                           "technique": cible_technique.id,
                           "verdict": getattr(execution.verdict, "value",
                                              execution.verdict),
                           "bloque": est_ferme(execution), "preuve": preuve.id})
    return execution, preuve


def _resoudre(finding: Finding, catalogue: Optional[dict]) -> Technique:
    """Retrouve la technique d'origine depuis le catalogue."""
    from piege.erreurs import TechniqueInconnue

    for identifiant in finding.technique_ids:
        technique = (catalogue or {}).get(identifiant)
        if technique is not None:
            return technique
    raise TechniqueInconnue(
        "technique d'origine introuvable pour le finding %s : fournir la "
        "technique ou le catalogue" % finding.id, code="technique_inconnue",
        details={"regle": "correctif.rejeu"})


def _campagne_rejeu(finding: Finding, mandat: Any, graine: int) -> Campagne:
    """Campagne de rejeu, distincte de la campagne d'origine (traçabilité)."""
    return Campagne(id="CMP-REJEU-%s" % finding.id.split("-")[-1],
                    mandat_id=mandat.id, application_id=finding.application_id,
                    tenant_id=finding.tenant_id, type=TypeCampagne.REJEU,
                    graine=graine, statut=StatutCampagne.EN_COURS,
                    debutee_le=maintenant_utc(),
                    techniques_prevues=list(finding.technique_ids))


def _preuve(execution: Execution, finding: Finding, campagne: Campagne,
            dossier: str) -> Preuve:
    """Construit la preuve immuable du rejeu (empreinte de l'exécution)."""
    contenu = canonical({"execution": execution.vers_dict(),
                         "finding": finding.id, "date": maintenant_utc()})
    return Preuve(
        id="PRV-%s-%s" % (campagne.id, execution.technique_id),
        type="rejeu", campagne_id=campagne.id, tenant_id=finding.tenant_id,
        chemin=chemin_preuve(campagne.id, execution.technique_id, dossier),
        empreinte=empreinte(contenu), date=maintenant_utc(),
        verbatim=(execution.reponse_brute or "")[:2000])


def est_ferme(execution: Execution) -> bool:
    """Une attaque est fermée si le rejeu a été **statué** et n'est pas un succès.

    Deux cas comptent comme fermés : le verdict est un échec, ou la passerelle a
    refusé la sonde (exécution `refuse`). Un verdict absent — juge défaillant,
    exécution non statuée — ne ferme rien : on ne prouve pas une fermeture par
    une absence de mesure.
    """
    if execution.statut == "refuse":
        return True
    return execution.verdict is VerdictValeur.ECHOUE


def fermer(finding: Finding, preuve: Preuve, execution: Optional[Execution] = None,
           correctif: Optional[Correctif] = None,
           effet_de_bord: str = "", regression: str = "") -> Finding:
    """Ferme une découverte : preuve, date, correctif et effets signalés.

    L'effet de bord et la régression sont écrits **dans la même ligne** que la
    fermeture (EF-44, EF-45) : un rapport ne peut pas annoncer une faille fermée
    sans dire ce que le correctif a coûté par ailleurs.
    """
    if execution is not None and not est_ferme(execution):
        finding.statut = StatutFinding.OUVERT
        if correctif is not None:
            correctif.statut = StatutCorrectif.REFUSE
            correctif.regression = "rejeu encore réussi"
        return finding
    finding.statut = StatutFinding.FERME
    finding.ferme_le = maintenant_utc()
    if preuve.id not in finding.preuve_fermeture_ids:
        finding.preuve_fermeture_ids.append(preuve.id)
    if correctif is not None:
        correctif.statut = StatutCorrectif.REJOUE
        correctif.rejoue_le = maintenant_utc()
        correctif.effet_de_bord = effet_de_bord
        correctif.regression = regression
        if correctif.id not in finding.correctif_ids:
            finding.correctif_ids.append(correctif.id)
    return finding
