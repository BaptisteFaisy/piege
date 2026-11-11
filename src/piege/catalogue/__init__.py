"""Piège — catalogue des techniques d'attaque : chargement et applicabilité.

Le catalogue est un ensemble de fichiers de données (un par famille) : ajouter
une technique ne demande **aucune modification de code** (spécification §18.4,
KPI-4, recette R18). Ce module charge, indexe, filtre et mesure la couverture.

Point d'entrée : `charger_catalogue(dossier) -> dict[identifiant, Technique]`.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional

from piege.catalogue.chargeur import ErreurYaml, charger_fichier
from piege.catalogue.erreurs import CatalogueInvalide, TechniqueInvalide
from piege.catalogue.modele import vers_techniques
from piege.types import (Application, Environnement, Famille, Mandat,
                         ProductionAutorisee, Technique)

__all__ = ["charger_catalogue", "charger_fichier_catalogue", "par_famille",
           "techniques_applicables", "couverture", "FAMILLES",
           "PRECONDITION_DEPOT", "budget_total"]

FAMILLES = tuple(membre.value for membre in Famille)
PRECONDITION_DEPOT = "depot_document_autorise"
EXTENSIONS = (".yaml", ".yml")


def charger_fichier_catalogue(chemin: str) -> list[Technique]:
    """Charge un fichier de catalogue ; les erreurs nomment le fichier."""
    try:
        document = charger_fichier(chemin)
    except (OSError, UnicodeError) as exc:
        raise CatalogueInvalide("fichier illisible : %s" % exc, fichier=chemin,
                                regle="catalogue.lecture") from exc
    except ErreurYaml as exc:
        raise CatalogueInvalide("YAML hors sous-ensemble : %s" % exc,
                                fichier=chemin, regle="catalogue.yaml") from exc
    try:
        return list(vers_techniques(document, chemin))
    except TechniqueInvalide as exc:
        raise CatalogueInvalide(str(exc), fichier=chemin,
                                regle=exc.details.get("regle", ""),
                                details={"technique": exc.technique_id}) from exc


def charger_catalogue(dossier: str = "catalogue") -> dict[str, Technique]:
    """Charge tous les fichiers `famille-*.yaml` d'un dossier, indexés par id."""
    if not os.path.isdir(dossier):
        raise CatalogueInvalide("dossier de catalogue introuvable : %s" % dossier,
                                regle="catalogue.dossier")
    catalogue: dict[str, Technique] = {}
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(EXTENSIONS):
            continue
        chemin = os.path.join(dossier, nom)
        for technique in charger_fichier_catalogue(chemin):
            if technique.id in catalogue:
                raise CatalogueInvalide(
                    "identifiant de technique dupliqué : %s" % technique.id,
                    fichier=chemin, regle="catalogue.doublon")
            catalogue[technique.id] = technique
    if not catalogue:
        raise CatalogueInvalide("aucune technique trouvée dans %s" % dossier,
                                regle="catalogue.vide")
    return catalogue


def par_famille(techniques: Iterable[Technique]) -> dict[str, list[Technique]]:
    """Regroupe les techniques par famille (les 8 familles, même vides)."""
    groupes: dict[str, list[Technique]] = {famille: [] for famille in FAMILLES}
    for technique in techniques:
        groupes.setdefault(technique.famille.value, []).append(technique)
    return groupes


def budget_total(techniques: Iterable[Technique]) -> dict[str, int]:
    """Budgets d'appels : total, et total hors techniques `jamais` en prod."""
    total = jamais = 0
    for technique in techniques:
        total += technique.budget_appels
        if technique.production is ProductionAutorisee.JAMAIS:
            jamais += technique.budget_appels
    return {"appels": total, "appels_hors_production": total - jamais,
            "appels_jamais": jamais}


def _preconditions_satisfaites(technique: Technique, application: Application,
                               corpus_legitime: bool) -> Optional[str]:
    """Motif de non-applicabilité lié aux préconditions, ou `None`."""
    for precondition in technique.preconditions:
        if precondition == PRECONDITION_DEPOT and not application.depot_document_autorise:
            return "depot_document_non_autorise"
        if precondition == "corpus_legitime" and not corpus_legitime:
            return "corpus_legitime_absent"
    if technique.famille is Famille.G and not corpus_legitime:
        return "corpus_legitime_absent"
    return None


def _environnement_autorise(technique: Technique, application: Application,
                            mandat: Optional[Mandat]) -> Optional[str]:
    """Motif lié à l'environnement ou à la production, ou `None`."""
    environnement = application.environnement
    if environnement not in technique.environnement:
        return "environnement_non_couvert"
    if mandat is not None and environnement not in mandat.environnements:
        return "environnement_hors_mandat"
    if environnement is Environnement.PROD:
        if technique.production is ProductionAutorisee.JAMAIS:
            return "production_interdite_par_le_catalogue"
        if mandat is not None and not mandat.production_autorisee:
            return "production_non_autorisee"
    return None


def techniques_applicables(application: Application, mandat: Optional[Mandat],
                           catalogue: dict[str, Technique],
                           corpus_legitime: bool = False) -> list[Technique]:
    """Techniques applicables à une cible sous un mandat donné (EF-02)."""
    applicables = []
    for identifiant in sorted(catalogue):
        technique = catalogue[identifiant]
        if mandat is not None and mandat.perimetre_techniques \
                and identifiant not in mandat.perimetre_techniques:
            continue
        if _environnement_autorise(technique, application, mandat):
            continue
        if _preconditions_satisfaites(technique, application, corpus_legitime):
            continue
        applicables.append(technique)
    return applicables


def couverture(application: Application, mandat: Optional[Mandat],
               catalogue: dict[str, Technique],
               corpus_legitime: bool = False) -> dict[str, Any]:
    """Couverture prévue avant exécution (KPI-6) : taux et motifs d'exclusion."""
    exclusions: dict[str, list[str]] = {}
    applicables = []
    for identifiant in sorted(catalogue):
        technique = catalogue[identifiant]
        motif = _motif_exclusion(technique, application, mandat, corpus_legitime)
        if motif:
            exclusions.setdefault(motif, []).append(identifiant)
        else:
            applicables.append(identifiant)
    total = len(catalogue)
    return {"applicables": len(applicables), "total": total,
            "taux": round(len(applicables) / total, 4) if total else 0.0,
            "identifiants": applicables,
            "exclusions": {motif: sorted(ids) for motif, ids in exclusions.items()}}


def _motif_exclusion(technique: Technique, application: Application,
                     mandat: Optional[Mandat], corpus_legitime: bool) -> str:
    """Premier motif d'exclusion d'une technique, chaîne vide si applicable."""
    if mandat is not None and mandat.perimetre_techniques \
            and technique.id not in mandat.perimetre_techniques:
        return "hors_perimetre_du_mandat"
    return (_environnement_autorise(technique, application, mandat)
            or _preconditions_satisfaites(technique, application, corpus_legitime)
            or "")
