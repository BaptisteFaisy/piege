#!/usr/bin/env python3
"""Piège — table de preuve des recettes (R1..R20) : un test exécutable par exigence.

Chaque recette du cahier des charges doit pouvoir être **prouvée**, pas
affirmée. Ce script relie chaque recette à ses tests, les **exécute**, et sort
le résultat : la preuve est un résultat de test, daté.

Deux sources de liaison :
- les tests **nommés d'après la recette** (`test_r14_vue_par_tenant`) sont
  découverts automatiquement — ils font foi ;
- les recettes qui ne portent pas encore de test nommé sont reliées aux
  fichiers de test qui couvrent le comportement (complément explicite, ci-dessous).

Usage :
    python3 scripts/preuves/recettes.py             # tableau, tests exécutés
    python3 scripts/preuves/recettes.py --json      # sortie machine
    python3 scripts/preuves/recettes.py --markdown  # section pour la doc
    python3 scripts/preuves/recettes.py --sans-executer  # liaison seule
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Optional

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAHIER = os.path.join(RACINE, "docs", "fr", "CAHIER-DES-CHARGES.md")
DOSSIER_TESTS = os.path.join(RACINE, "tests")

# Complément explicite : recettes sans test nommé, et fichiers qui les prouvent.
COMPLEMENT = {
    "R5": ["tests/test_moteur_arret.py"],
    "R6": ["tests/test_demo_bout_en_bout.py", "tests/test_severite.py"],
    "R7": ["tests/test_famille_f.py"],
    "R8": ["tests/test_famille_g.py"],
    "R9": ["tests/test_famille_g.py", "tests/test_corpus_benchmark.py"],
    "R11": ["tests/test_correctifs_boucle.py", "tests/test_correctifs.py"],
    "R12": ["tests/test_correctifs_boucle.py"],
    "R17": ["tests/test_cout_mesure.py"],
    "R19": ["tests/test_correctifs_boucle.py", "tests/test_api.py"],
    "R20": ["tests/test_multi_tenant.py", "tests/test_stockage_local.py"],
}
MOTIF_TEST = re.compile(r"^\s+def (test_r(\d+)_[A-Za-z0-9_]+)")
MOTIF_CLASSE = re.compile(r"^class (\w+)")


def lire_recettes() -> dict:
    """Lit les recettes (R1..R20) du cahier des charges : exigence et attendu."""
    recettes = {}
    try:
        with open(CAHIER, encoding="utf-8") as f:
            for ligne in f:
                morceaux = [m.strip() for m in ligne.strip().strip("|").split("|")]
                if len(morceaux) >= 3 and re.fullmatch(r"R\d+", morceaux[0]):
                    recettes[morceaux[0]] = {"exigence": morceaux[1],
                                            "attendu": morceaux[2]}
    except OSError:
        return {}
    return recettes


def decouvrir_nommes() -> dict:
    """Trouve les tests nommés d'après une recette (`test_rN_…`).

    L'identifiant pytest porte la classe : sans elle, le nœud ne se résout pas
    et la preuve serait vide — un test de méthode s'appelle
    `fichier::Classe::test`.
    """
    trouves = {}
    for nom in sorted(os.listdir(DOSSIER_TESTS)):
        if not nom.startswith("test_") or not nom.endswith(".py"):
            continue
        chemin = os.path.join(DOSSIER_TESTS, nom)
        classe = ""
        with open(chemin, encoding="utf-8") as f:
            for ligne in f:
                entete = MOTIF_CLASSE.match(ligne)
                if entete:
                    classe = entete.group(1)
                    continue
                trouve = MOTIF_TEST.match(ligne)
                if not trouve:
                    continue
                noeud = "tests/%s::%s::%s" % (nom, classe, trouve.group(1)) \
                    if classe else "tests/%s::%s" % (nom, trouve.group(1))
                trouves.setdefault("R%d" % int(trouve.group(2)), []).append(noeud)
    return trouves


def lier(recettes: dict) -> dict:
    """Associe à chaque recette ses tests : nommés d'abord, complément ensuite."""
    nommes = decouvrir_nommes()
    liaison = {}
    for identifiant in recettes:
        preuves = list(nommes.get(identifiant, []))
        for fichier in COMPLEMENT.get(identifiant, []):
            chemin = os.path.join(RACINE, fichier)
            if os.path.isfile(chemin) and fichier not in preuves:
                preuves.append(fichier)
        liaison[identifiant] = sorted(preuves)
    return liaison


def executer(preuves: list) -> dict:
    """Exécute les tests proofs et rend, par test, son résultat."""
    if not preuves:
        return {}
    commande = [sys.executable, "-m", "pytest", "-q", "-rA", "--no-header",
                "-p", "no:cacheprovider"] + preuves
    resultat = subprocess.run(commande, cwd=RACINE, capture_output=True,
                              text=True, timeout=900)
    etats = {}
    for ligne in resultat.stdout.splitlines():
        morceaux = ligne.split()
        if len(morceaux) < 2 or morceaux[0] not in ("PASSED", "FAILED", "ERROR",
                                                    "SKIPPED", "XFAIL", "XPASS"):
            continue
        etats[morceaux[1]] = morceaux[0]
    if not etats and resultat.returncode != 0:
        # Aucun verdict alors que pytest a échoué : un nœud invalide, par
        # exemple. Une preuve muette est pire qu'une preuve absente — on le dit.
        detail = (resultat.stdout + resultat.stderr).strip().splitlines()[-3:]
        raise RuntimeError("exécution des preuves impossible : %s"
                           % " / ".join(detail))
    return etats


def verdict_fichier(etats: dict, fichier: str) -> str:
    """Verdict d'un fichier de test : tous ses tests passent-ils ?"""
    ids = [cle for cle in etats if cle.startswith(fichier + "::")]
    if not ids:
        return "ABSENT"
    verdicts = [etats[cle] for cle in ids]
    if all(v == "PASSED" for v in verdicts):
        return "PASSED"
    if any(v in ("FAILED", "ERROR") for v in verdicts):
        return "FAILED"
    return verdicts[0]


def verdict_preuve(etats: dict, preuve: str) -> str:
    """Verdict d'une preuve : un test nommé ou un fichier de tests."""
    if "::" in preuve:
        return etats.get(preuve, "ABSENT")
    return verdict_fichier(etats, preuve)


def resultats(liaison: dict, etats: dict) -> dict:
    """Statut par recette : prouvé si tous ses tests passent."""
    sortie = {}
    for identifiant, preuves in liaison.items():
        if not preuves:
            sortie[identifiant] = {"statut": "a_prouver", "tests": []}
            continue
        verdicts = [verdict_preuve(etats, preuve) for preuve in preuves]
        if all(v == "PASSED" for v in verdicts):
            statut = "prouve"
        elif any(v in ("FAILED", "ERROR") for v in verdicts):
            statut = "en_echec"
        else:
            statut = "a_prouver"
        sortie[identifiant] = {"statut": statut, "tests": preuves,
                               "verdicts": verdicts}
    return sortie


def _statut(preuves: list, etats: dict) -> str:
    """Statut d'une recette : prouvé, en échec, ou à prouver."""
    if not preuves:
        return "a_prouver"
    verdicts = [verdict_preuve(etats, preuve) for preuve in preuves]
    if all(v == "PASSED" for v in verdicts):
        return "prouve"
    if any(v in ("FAILED", "ERROR") for v in verdicts):
        return "en_echec"
    return "a_prouver"


def tableau(recettes: dict, liaison: dict, etats: dict) -> str:
    """Tableau texte de la preuve, une ligne par recette."""
    lignes = ["%-5s %-46s %-9s %s" % ("Recette", "Exigence", "Statut", "Preuve")]
    for identifiant in sorted(recettes, key=lambda r: int(r[1:])):
        preuves = liaison.get(identifiant, [])
        verdict = _statut(preuves, etats)
        extrait = ", ".join(os.path.basename(p).replace(".py", "")
                            for p in preuves[:3]) or "—"
        lignes.append("%-5s %-46s %-9s %s" % (
            identifiant, recettes[identifiant]["exigence"][:46], verdict,
            extrait))
    return "\n".join(lignes)


def markdown(recettes: dict, liaison: dict, etats: dict) -> str:
    """Section Markdown pour la documentation (une ligne par recette)."""
    lignes = ["## Recettes (R1–R20) — preuve exécutable", "",
              "Chaque recette est reliée à ses tests ; la preuve est le résultat "
              "de leur exécution, pas une déclaration.", "",
              "| Recette | Exigence | Attendu | Preuve (test) | Résultat |",
              "|---|---|---|---|---|"]
    for identifiant in sorted(recettes, key=lambda r: int(r[1:])):
        preuves = liaison.get(identifiant, [])
        verdict = _statut(preuves, etats)
        nom_tests = ", ".join("`%s`" % _libelle(p) for p in preuves[:3])
        lignes.append("| %s | %s | %s | %s | **%s** |" % (
            identifiant, recettes[identifiant]["exigence"],
            recettes[identifiant]["attendu"], nom_tests or "—", verdict))
    return "\n".join(lignes)


def _libelle(preuve: str) -> str:
    """Libellé court d'une preuve : le fichier, puis le test nommé s'il y en a un."""
    morceaux = preuve.split("::")
    if len(morceaux) == 1:
        return os.path.basename(morceaux[0])
    return "%s::%s" % (os.path.basename(morceaux[0]), morceaux[-1])


def main(argv: Optional[list] = None) -> int:
    """Point d'entrée : lie, exécute et restitue la preuve des recettes."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", action="store_true", dest="en_json")
    analyseur.add_argument("--markdown", action="store_true", dest="en_markdown")
    analyseur.add_argument("--sans-executer", action="store_true",
                           dest="sans_executer")
    args = analyseur.parse_args(argv)

    recettes = lire_recettes()
    if not recettes:
        print("cahier des charges introuvable : %s" % CAHIER, file=sys.stderr)
        return 1
    liaison = lier(recettes)
    etats = {} if args.sans_executer else executer(
        [preuve for preuves in liaison.values() for preuve in preuves])

    if args.en_json:
        print(json.dumps({"recettes": recettes, "preuves": liaison,
                          "resultats": resultats(liaison, etats)},
                         ensure_ascii=False, indent=2))
    elif args.en_markdown:
        print(markdown(recettes, liaison, etats))
    else:
        print(tableau(recettes, liaison, etats))
        prouvées = sum(1 for v in resultats(liaison, etats).values()
                       if v["statut"] == "prouve")
        print("\n%d/%d recettes prouvées" % (prouvées, len(recettes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
