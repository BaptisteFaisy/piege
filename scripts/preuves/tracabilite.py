#!/usr/bin/env python3
"""Piège — statuts de traçabilité recalculés (EF-*, ENF-*, KPI-*).

`docs/TRACEABILITY.md` est append-only : les statuts « Status » reflètent
l'état **à l'ouverture du lot**, pas au merge. Ce script **recalcule** le
statut de chaque ligne à partir de ce qui existe réellement (fichier `Code`
présent ? test `Tests` présent ?), sans réécrire le document : il produit une
section « Statuts vérifiés » à recopier en fin de document, et liste les
incohérences quand l'état déclaré ne correspond plus à la réalité.

Usage :
    python3 scripts/preuves/tracabilite.py            # section Markdown
    python3 scripts/preuves/tracabilite.py --json     # sortie machine
    python3 scripts/preuves/tracabilite.py --ecarts   # lignes à corriger
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC = os.path.join(RACINE, "docs", "TRACEABILITY.md")
LIGNE = re.compile(r"^\|\s*(EF|ENF|KPI)-\S+\s*\|")
MOTIF_CHEMIN = re.compile(r"`([^`]+)`")
MOTIF_RECETTE = re.compile(r"\bR(\d+)\b")


def _existe(chemin: str) -> bool:
    """Vrai si un fichier/dossier (référencé par le document) existe."""
    brut = chemin.strip().rstrip("/")
    if not brut:
        return False
    return os.path.exists(os.path.join(RACINE, brut))


def _chemins(cellule: str) -> set:
    """Chemins mentionnés dans une cellule (entre backticks)."""
    return {m.strip() for m in MOTIF_CHEMIN.findall(cellule) if "/" in m or "." in m}


def _code_present(cellule: str) -> bool:
    """Vrai si au moins un chemin de la colonne « Code » existe."""
    if not cellule or cellule.strip() in ("—", "-"):
        return False
    for chemin in _chemins(cellule):
        if _existe(chemin):
            return True
    return False


def _tests_present(cellule: str) -> bool:
    """Vrai si la colonne « Tests » pointe vers une preuve exécutable.

    Sont des preuves : un fichier de test existant, une recette (déjà prouvée
    par `scripts/preuves/recettes.py`), ou la mention du validateur de
    catalogue (présent).
    """
    if not cellule or cellule.strip() in ("—", "-"):
        return False
    if "catalogue validator" in cellule and _existe("src/piege/catalogue/valideur.py"):
        return True
    if MOTIF_RECETTE.search(cellule):
        return True
    for chemin in _chemins(cellule):
        if chemin.startswith("tests/") and _existe(chemin):
            return True
    return False


def calculer_statut(code: bool, tests: bool) -> str:
    """Statut recalculé : done, partial ou todo."""
    if code and tests:
        return "done"
    if code or tests:
        return "partial"
    return "todo"


def analyser(contenu: str) -> dict:
    """Analyse les trois tables : une ligne par exigence, statut recalculé."""
    resultats = {}
    section = None
    for ligne in contenu.splitlines():
        if ligne.startswith("## Functional"):
            section = "EF"
            continue
        if ligne.startswith("## Non-functional"):
            section = "ENF"
            continue
        if ligne.startswith("## Indicators"):
            section = "KPI"
            continue
        if ligne.startswith("## ") or ligne.startswith("# "):
            section = None
            continue
        if not section or not LIGNE.match(ligne):
            continue
        colonnes = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(colonnes) < 6:
            continue
        identifiant, exigence, code, tests, lot, statut = colonnes[:6]
        recalcul = calculer_statut(_code_present(code), _tests_present(tests))
        resultats[identifiant] = {
            "exigence": exigence, "code": code, "tests": tests,
            "lot": lot, "declare": statut, "recalcule": recalcul,
        }
    return resultats


def ecarts(resultats: dict) -> list:
    """Lignes où le statut déclaré ne correspond plus au statut recalculé.

    `todo` déclaré alors que code ET test existent : le document ment en
    défaveur du projet. `done` déclaré alors que rien n'existe : le document
    ment en faveur. Les deux valent une correction.
    """
    sortie = []
    for identifiant, ligne in resultats.items():
        if ligne["declare"] != ligne["recalcule"]:
            sortie.append((identifiant, ligne))
    return sortie


def section_markdown(resultats: dict) -> str:
    """Section « Statuts vérifiés » à copier en fin de TRACEABILITY.md."""
    lignes = ["## Statuts vérifiés — recalculés sur le dépôt (généré)", "",
              "Statut recalculé à partir de l'existence réelle du **code** et des "
              "**tests** référencés, indépendamment du statut déclaré à l'ouverture "
              "des lots. `done` = code ET test présents ; `partial` = l'un des "
              "deux ; `todo` = aucun des deux ne référence de code ni de test "
              "(une ligne peut être implémentée sans que ce document ait "
              "renseigné ses colonnes Code/Tests).", ""]
    for prefixe, titre in (("EF", "Exigences fonctionnelles"),
                           ("ENF", "Exigences non fonctionnelles"),
                           ("KPI", "Indicateurs")):
        lignes.append("| %s | %s |" % (prefixe, titre))
        lignes.append("|---|---|")
        for identifiant, ligne in sorted(resultats.items(),
                                         key=lambda kv: kv[0]):
            if not identifiant.startswith(prefixe):
                continue
            lignes.append("| %s | %s (%s) |" % (identifiant, ligne["recalcule"],
                                                _note(ligne)))
        lignes.append("")
    return "\n".join(lignes)


def _note(ligne: dict) -> str:
    """Motif court : ce qui a changé par rapport au statut déclaré."""
    if ligne["declare"] == ligne["recalcule"]:
        return "inchangé"
    return "déclaré %s" % ligne["declare"]


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", action="store_true", dest="en_json")
    analyseur.add_argument("--ecarts", action="store_true")
    args = analyseur.parse_args(argv)

    with open(DOC, encoding="utf-8") as f:
        contenu = f.read()
    resultats = analyser(contenu)
    if not resultats:
        print("aucune exigence analysée", file=sys.stderr)
        return 2
    if args.en_json:
        print(json.dumps({"resultats": resultats, "ecarts": ecarts(resultats)},
                         ensure_ascii=False, indent=1))
    elif args.ecarts:
        for identifiant, ligne in ecarts(resultats):
            print("%-8s déclaré=%s recalculé=%s — %s"
                  % (identifiant, ligne["declare"], ligne["recalcule"],
                     ligne["exigence"]))
        print("\n%d écart(s) au total" % len(ecarts(resultats)))
    else:
        print(section_markdown(resultats))
    return 0


if __name__ == "__main__":
    sys.exit(main())