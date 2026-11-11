"""Piège — validateur du catalogue : le schéma, l'annexe A et les totaux.

Commande : `python3 -m piege.catalogue.valideur catalogue [--resume] [--json]`
Codes : 0 conforme, 1 non conforme.

**Écart documenté avec la spécification.** L'annexe F.4 annonce 288 appels dont
234 hors production. La somme réelle de la colonne « budget appels » de
l'annexe A est **311**, dont **175** pour les techniques qui ne sont pas
`production: jamais` (136 pour celles qui le sont). Les données par technique
de l'annexe A font foi : ce sont elles qui bornent l'exécution. Les totaux
attendus ici sont donc 311 et 175, et l'écart est signalé dans le rapport
(`docs/TRACEABILITY.md`, ligne ENF-03).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Optional

from piege.catalogue import (PRECONDITION_DEPOT, budget_total,
                             charger_catalogue, par_famille)
from piege.types import Famille, ProductionAutorisee, Technique

__all__ = ["ANNEXE_A", "valider", "main", "TOTAUX_ATTENDUS"]

# Annexe A : identifiant → (famille, environnements, production, appels, tours).
ANNEXE_A = {
    "A1": ("injection_directe", "test,preprod", "sur_mandat", 2, 1),
    "A2": ("injection_directe", "test,preprod", "sur_mandat", 3, 2),
    "A3": ("injection_directe", "test,preprod", "sur_mandat", 4, 1),
    "A4": ("injection_directe", "test,preprod", "sur_mandat", 8, 5),
    "A5": ("injection_directe", "test,preprod", "sur_mandat", 4, 2),
    "A6": ("injection_directe", "test,preprod", "sur_mandat", 3, 1),
    "A7": ("injection_directe", "test,preprod", "sur_mandat", 3, 2),
    "A8": ("injection_directe", "test,preprod", "sur_mandat", 2, 1),
    "A9": ("injection_directe", "test,preprod", "sur_mandat", 3, 2),
    "B1": ("injection_indirecte", "test", "jamais", 6, 2),
    "B2": ("injection_indirecte", "test,preprod", "sur_mandat", 5, 2),
    "B3": ("injection_indirecte", "test", "jamais", 5, 2),
    "B4": ("injection_indirecte", "test", "jamais", 4, 1),
    "B5": ("injection_indirecte", "test", "jamais", 4, 1),
    "B6": ("injection_indirecte", "test,preprod", "sur_mandat", 5, 2),
    "B7": ("injection_indirecte", "test,preprod", "sur_mandat", 7, 4),
    "B8": ("injection_indirecte", "test", "jamais", 6, 3),
    "B9": ("injection_indirecte", "test", "jamais", 4, 1),
    "B10": ("injection_indirecte", "test,preprod", "sur_mandat", 3, 1),
    "C1": ("extraction", "test,preprod", "sur_mandat", 3, 2),
    "C2": ("extraction", "test,preprod", "sur_mandat", 3, 2),
    "C3": ("extraction", "test", "jamais", 4, 2),
    "C4": ("extraction", "test,preprod", "sur_mandat", 3, 2),
    "C5": ("extraction", "test,preprod", "sur_mandat", 20, 20),
    "C6": ("extraction", "test,preprod", "sur_mandat", 6, 4),
    "C7": ("extraction", "test,preprod", "sur_mandat", 4, 2),
    "C8": ("extraction", "test,preprod", "sur_mandat", 3, 2),
    "D1": ("perimetre", "test", "jamais", 5, 2),
    "D2": ("perimetre", "test,preprod", "sur_mandat", 6, 3),
    "D3": ("perimetre", "test", "jamais", 5, 2),
    "D4": ("perimetre", "test,preprod", "sur_mandat", 6, 3),
    "D5": ("perimetre", "test,preprod", "sur_mandat", 8, 4),
    "D6": ("perimetre", "test", "jamais", 10, 10),
    "D7": ("perimetre", "test", "jamais", 4, 2),
    "E1": ("garde_fous", "test,preprod", "sur_mandat", 4, 2),
    "E2": ("garde_fous", "test,preprod", "sur_mandat", 4, 2),
    "E3": ("garde_fous", "test,preprod", "sur_mandat", 4, 2),
    "E4": ("garde_fous", "test,preprod", "sur_mandat", 4, 2),
    "E5": ("garde_fous", "test,preprod", "sur_mandat", 6, 2),
    "E6": ("garde_fous", "test,preprod", "sur_mandat", 3, 1),
    "F1": ("empoisonnement_corpus", "test", "jamais", 6, 2),
    "F2": ("empoisonnement_corpus", "test", "jamais", 6, 2),
    "F3": ("empoisonnement_corpus", "test", "jamais", 6, 2),
    "F4": ("empoisonnement_corpus", "test", "jamais", 7, 3),
    "F5": ("empoisonnement_corpus", "test", "jamais", 12, 3),
    "F6": ("empoisonnement_corpus", "test", "jamais", 9, 3),
    "F7": ("empoisonnement_corpus", "test", "jamais", 8, 3),
    "F8": ("empoisonnement_corpus", "test", "jamais", 10, 3),
    "G1": ("faux_refus", "test,preprod,production", "oui", 1, 1),
    "G2": ("faux_refus", "test,preprod,production", "oui", 1, 1),
    "G3": ("faux_refus", "test,preprod,production", "oui", 1, 1),
    "G4": ("faux_refus", "test,preprod", "sur_mandat", 2, 1),
    "G5": ("faux_refus", "test,preprod", "sur_mandat", 6, 5),
    "G6": ("faux_refus", "test,preprod", "sur_mandat", 2, 1),
    "G7": ("faux_refus", "test,preprod,production", "oui", 1, 1),
    "H1": ("abus_fonctionnel", "test,preprod", "sur_mandat", 4, 2),
    "H2": ("abus_fonctionnel", "test", "jamais", 10, 3),
    "H3": ("abus_fonctionnel", "test,preprod", "sur_mandat", 3, 2),
    "H4": ("abus_fonctionnel", "test,preprod", "sur_mandat", 15, 12),
    "H5": ("abus_fonctionnel", "test", "jamais", 5, 3),
}

TOTAUX_ATTENDUS = {"appels": 311, "appels_hors_production": 175,
                   "appels_jamais": 136}

_DONNEE_PERSONNELLE = re.compile(
    r"(\b\d{1,2}\s?[./]\s?\d{2}\s?[./]\s?(19|20)\d{2}\b"      # date de naissance
    r"|\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\b"      # numéro de sécurité sociale
    r"|[\w.+-]+@[\w-]+\.[\w.]+)", re.I)                        # courriel


def _verifier_identifiants(catalogue: dict) -> list[str]:
    """Jeu d'identifiants exactement égal à l'annexe A."""
    erreurs = []
    manquants = sorted(set(ANNEXE_A) - set(catalogue))
    inattendus = sorted(set(catalogue) - set(ANNEXE_A))
    if manquants:
        erreurs.append("techniques manquantes : %s" % ", ".join(manquants))
    if inattendus:
        erreurs.append("techniques hors annexe A : %s" % ", ".join(inattendus))
    return erreurs


def _verifier_annexe_a(technique: Technique) -> list[str]:
    """Une technique doit reprendre exactement sa ligne d'annexe A."""
    famille, environnements, production, appels, tours = ANNEXE_A[technique.id]
    erreurs = []
    if technique.famille.value != famille:
        erreurs.append("%s : famille %s attendue, %s trouvée"
                       % (technique.id, famille, technique.famille.value))
    attendus = [e.strip() for e in environnements.split(",")]
    trouves = [e.value for e in technique.environnement]
    if trouves != attendus:
        erreurs.append("%s : environnements %s attendus, %s trouvés"
                       % (technique.id, attendus, trouves))
    if technique.production.value != production:
        erreurs.append("%s : production %s attendue, %s trouvée"
                       % (technique.id, production, technique.production.value))
    if technique.budget_appels != appels:
        erreurs.append("%s : budget_appels %d attendu, %d trouvé"
                       % (technique.id, appels, technique.budget_appels))
    if technique.tours_max != tours:
        erreurs.append("%s : tours_max %d attendu, %d trouvé"
                       % (technique.id, tours, technique.tours_max))
    return erreurs


def _verifier_famille(technique: Technique, dossier: str) -> list[str]:
    """Règles propres aux familles F (dépôt) et G (corpus légitime)."""
    erreurs = []
    if technique.famille is Famille.F:
        if PRECONDITION_DEPOT not in technique.preconditions:
            erreurs.append("%s : précondition %s requise"
                           % (technique.id, PRECONDITION_DEPOT))
        if not technique.gabarit_document:
            erreurs.append("%s : gabarit_document requis" % technique.id)
        else:
            chemin = os.path.join(dossier, technique.gabarit_document)
            if not os.path.isfile(chemin):
                erreurs.append("%s : gabarit introuvable %s"
                               % (technique.id, technique.gabarit_document))
        if "relais" not in technique.mesures:
            erreurs.append("%s : mesure 'relais' requise" % technique.id)
    if technique.famille is Famille.G:
        if not technique.mesures or technique.mesures[0] != "refus":
            erreurs.append("%s : la première mesure doit être 'refus', trouvées %s"
                           % (technique.id, technique.mesures))
    return erreurs


def _verifier_contenu(technique: Technique) -> list[str]:
    """Sondes et objectifs non vides, sans donnée personnelle réelle (ENF-07)."""
    erreurs = []
    for champ, valeur in (("objectif", technique.objectif),
                          ("sonde_initiale", technique.sonde_initiale),
                          ("juge_reussi_si", technique.juge_reussi_si)):
        if not str(valeur).strip():
            erreurs.append("%s : champ %s vide" % (technique.id, champ))
    for champ in ("objectif", "sonde_initiale"):
        trouve = _DONNEE_PERSONNELLE.search(str(getattr(technique, champ)))
        if trouve:
            erreurs.append("%s : donnée personnelle apparente dans %s (%s)"
                           % (technique.id, champ, trouve.group(0)))
    return erreurs


def valider(dossier: str = "catalogue") -> dict:
    """Valide un dossier de catalogue ; rend erreurs, totaux et résumé."""
    from piege.catalogue.erreurs import CatalogueInvalide

    try:
        catalogue = charger_catalogue(dossier)
    except CatalogueInvalide as exc:
        return {"conforme": False, "erreurs": [str(exc)], "totaux": {},
                "familles": {}}
    erreurs = _verifier_identifiants(catalogue)
    for identifiant in sorted(catalogue):
        technique = catalogue[identifiant]
        erreurs += _verifier_annexe_a(technique)
        erreurs += _verifier_famille(technique, dossier)
        erreurs += _verifier_contenu(technique)
    totaux = budget_total(catalogue.values())
    erreurs += _verifier_totaux(totaux)
    familles = {famille: len(membres)
                for famille, membres in par_famille(catalogue.values()).items()}
    return {"conforme": not erreurs, "erreurs": erreurs, "totaux": totaux,
            "familles": familles, "nombre": len(catalogue)}


def _verifier_totaux(totaux: dict) -> list[str]:
    """Les totaux doivent correspondre à la somme de l'annexe A."""
    erreurs = []
    for cle, attendue in TOTAUX_ATTENDUS.items():
        if totaux.get(cle) != attendue:
            erreurs.append("total %s : %s attendu, %s trouvé"
                           % (cle, attendue, totaux.get(cle)))
    return erreurs


def _resume(resultat: dict) -> str:
    """Résumé lisible : familles, totaux, verdict."""
    lignes = []
    for famille in sorted(resultat["familles"]):
        lignes.append("  %-24s %2d technique(s)"
                      % (famille, resultat["familles"][famille]))
    lignes.append("  total : %d technique(s)" % resultat.get("nombre", 0))
    for cle in ("appels", "appels_hors_production", "appels_jamais"):
        lignes.append("  %-22s %d appel(s)" % (cle, resultat["totaux"].get(cle, 0)))
    lignes.append("CONFORME" if resultat["conforme"] else "NON CONFORME")
    return "\n".join(lignes)


def main(argv: Optional[list[str]] = None) -> int:
    """Point d'entrée du validateur."""
    analyseur = argparse.ArgumentParser(prog="piege.catalogue.valideur")
    analyseur.add_argument("dossier", nargs="?", default="catalogue")
    analyseur.add_argument("--resume", action="store_true")
    analyseur.add_argument("--json", action="store_true")
    args = analyseur.parse_args(argv)
    resultat = valider(args.dossier)
    if args.json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2))
    elif args.resume:
        print(_resume(resultat))
    for erreur in resultat["erreurs"]:
        print("::error::%s" % erreur)
    return 0 if resultat["conforme"] else 1


if __name__ == "__main__":
    sys.exit(main())
