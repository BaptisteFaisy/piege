#!/usr/bin/env python3
"""Piège — harnais d'évaluation (`eval/cibles.json`) : précision du juge
et détection de bout en bout.

Usage :
    python3 eval/mesurer.py            # tableau de bord
    python3 eval/mesurer.py --json     # sortie machine

Entièrement hors ligne : aucun modèle, aucun réseau. Le juge déterministe sert
de référence ; le harnais accepte n'importe quel juge injecté (voir
`src/piege/agents/juge/evaluation.py`).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "src"))

from piege.agents.juge import (CIBLE_ACCORD, CIBLE_DETECTION,
                               CIBLE_FAUX_POSITIFS, charger_cibles,
                               mesurer_detection, mesurer_juge, rapport)


def tableau(resultat: dict) -> str:
    """Rendu lisible du rapport : juge, détection, conformité."""
    juge, det = resultat["juge"], resultat["detection"]
    lignes = [
        "# Harnais d'évaluation — Piège (§24)",
        "",
        "JDGE : %d transcriptions étiquetées à la main" % juge["n"],
        "  accord   %.1f %% (cible ≥ %.0f %%)" % (juge["accord"] * 100, CIBLE_ACCORD * 100),
        "  précision %.1f %% | rappel %.1f %% | F1 %.2f"
        % (juge["precision"] * 100, juge["rappel"] * 100, juge["f1"]),
        "  faux positifs %d | faux négatifs %d"
        % (juge["faux_positifs"], juge["faux_negatifs"]),
        "",
        "DÉTECTION : %d cibles vulnérables, %d cibles saines"
        % (det["vulnerables"], det["saines"]),
        "  fuites vues %d/%d (%.0f %%, cible ≥ %.0f %%)"
        % (det["fuites_vues"], det["vulnerables"],
           det["taux_detection"] * 100, CIBLE_DETECTION * 100),
        "  fausses découvertes %d/%d (%.0f %%, cible ≤ %.0f %%)"
        % (det["fausses_decouvertes"], det["saines"],
           det["taux_faux_positifs"] * 100, CIBLE_FAUX_POSITIFS * 100),
        "",
        "CONFORME : %s" % ("oui" if resultat["conforme"] else "non"),
    ]
    if juge["a_revoir"]:
        lignes.append("à revoir : %s" % ", ".join(juge["a_revoir"]))
    return "\n".join(lignes)


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", action="store_true", dest="en_json")
    analyseur.add_argument("--repertoire", default=os.path.join(RACINE, "eval"))
    args = analyseur.parse_args(argv)
    fixtures = charger_cibles(args.repertoire)
    if not fixtures:
        print("jeu introuvable : %s" % args.repertoire, file=sys.stderr)
        return 2
    resultat = rapport(fixtures)
    if args.en_json:
        print(json.dumps(resultat, ensure_ascii=False, indent=1))
    else:
        print(tableau(resultat))
    return 0 if resultat["conforme"] else 1


if __name__ == "__main__":
    sys.exit(main())