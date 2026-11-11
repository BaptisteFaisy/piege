"""Piège — point d'entrée en ligne de commande.

Quatre gestes, tous utilisables hors ligne (CONTRACTS-INTERFACES §15) :

    piege demo        campagne de démonstration sur la cible « Guichet RH »
    piege catalogue   liste les techniques et la couverture par famille
    piege rapport     rapport FR/EN de la dernière campagne locale
    piege validation  vérifie ce qu'un mandat autorise, sans rien envoyer

Codes de sortie : 0 succès, 1 erreur d'usage, 2 opération refusée ou
composant absent, 3 erreur interne.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from piege.erreurs import ErreurPiege

__all__ = ["main", "construire_analyseur"]

CODE_SUCCES, CODE_USAGE, CODE_REFUS, CODE_ERREUR = 0, 1, 2, 3


def construire_analyseur() -> argparse.ArgumentParser:
    """Analyseur de la commande `piege`."""
    analyseur = argparse.ArgumentParser(prog="piege", description=__doc__)
    sous = analyseur.add_subparsers(dest="commande", required=True)

    demo = sous.add_parser("demo", help="campagne de démonstration")
    demo.add_argument("--graine", type=int, default=20261111)
    demo.add_argument("--cible", default="demo/cible/guichet-rh.json")
    demo.add_argument("--catalogue", default="catalogue")
    demo.add_argument("--techniques", default="")
    demo.add_argument("--json", action="store_true", dest="en_json")

    catalogue = sous.add_parser("catalogue", help="liste les techniques")
    catalogue.add_argument("dossier", nargs="?", default="catalogue")
    catalogue.add_argument("--famille", default="")
    catalogue.add_argument("--resume", action="store_true")

    rapport = sous.add_parser("rapport", help="rapport d'une campagne")
    rapport.add_argument("--derniere", action="store_true")
    rapport.add_argument("--campagne", default="")
    rapport.add_argument("--langues", default="fr")

    validation = sous.add_parser("validation", help="périmètre d'un mandat")
    validation.add_argument("--mandat", required=True)
    validation.add_argument("--technique", default="")
    validation.add_argument("--donnees", default="donnees-locales")
    validation.add_argument("--json", action="store_true", dest="en_json")
    return analyseur


def main(argv: Optional[list[str]] = None) -> int:
    """Exécute la commande demandée et rend le code de sortie."""
    args = construire_analyseur().parse_args(argv)
    try:
        if args.commande == "demo":
            return _commande_demo(args)
        if args.commande == "catalogue":
            return _commande_catalogue(args)
        if args.commande == "rapport":
            return _commande_rapport(args)
        return _commande_validation(args)
    except ErreurPiege as erreur:
        print("REFUSÉ [%s] %s" % (erreur.code, erreur.message), file=sys.stderr)
        return CODE_REFUS
    except (ImportError, FileNotFoundError) as absence:
        print("COMPOSANT ABSENT : %s" % absence, file=sys.stderr)
        return CODE_REFUS


def _commande_demo(args) -> int:
    """Lance une campagne de démonstration, entièrement hors ligne."""
    from piege.moteur import executer_campagne
    from piege.moteur.demo import campagne_de_demonstration

    config = campagne_de_demonstration(
        graine=args.graine, cible_spec=_charger_json(args.cible),
        dossier_catalogue=args.catalogue,
        technique_ids=[t for t in args.techniques.split(",") if t])
    campagne = executer_campagne(config)
    if args.en_json:
        print(json.dumps(campagne.vers_dict(), ensure_ascii=False, indent=2))
    else:
        print("Campagne %s — %s — %d appel(s), %d jeton(s)"
              % (campagne.id, campagne.statut.value, campagne.appels,
                 campagne.jetons))
    return CODE_SUCCES


def _charger_json(chemin: str) -> dict:
    """Charge une spécification JSON ; dictionnaire vide si absente."""
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _commande_catalogue(args) -> int:
    """Liste les techniques du catalogue (KPI-4, KPI-6)."""
    from piege.catalogue import charger_catalogue, par_famille

    techniques = charger_catalogue(args.dossier)
    if args.famille:
        techniques = {k: v for k, v in techniques.items()
                      if v.famille.value.startswith(args.famille.lower())}
    if args.resume:
        for famille, membres in sorted(par_famille(techniques).items()):
            print("%-24s %2d technique(s)" % (famille, len(membres)))
        print("total : %d technique(s)" % len(techniques))
        return CODE_SUCCES
    for identifiant in sorted(techniques):
        technique = techniques[identifiant]
        print("%-4s %-22s appels=%-3d tours=%-3d prod=%s"
              % (identifiant, technique.nom[:22], technique.budget_appels,
                 technique.tours_max, technique.production.value))
    return CODE_SUCCES


def _commande_rapport(args) -> int:
    """Génère le rapport d'une campagne (lot 12)."""
    from piege.rapport import rapport_depuis_entrepot

    for langue in [l for l in args.langues.split(",") if l]:
        print(rapport_depuis_entrepot(campagne_id=args.campagne,
                                      derniere=args.derniere, langue=langue))
    return CODE_SUCCES


def _commande_validation(args) -> int:
    """Vérifie ce qu'un mandat autorise, sans envoyer la moindre sonde."""
    from piege.moteur.validation import valider_perimetre

    resultat = valider_perimetre(args.mandat, args.technique, args.donnees)
    if args.en_json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2))
        return CODE_SUCCES
    for ligne in resultat["lignes"]:
        print(ligne)
    return CODE_SUCCES if resultat["autorise"] else CODE_REFUS


if __name__ == "__main__":
    sys.exit(main())
