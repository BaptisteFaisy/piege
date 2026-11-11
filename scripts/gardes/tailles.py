#!/usr/bin/env python3
"""Garde de taille — fichiers < 500 lignes, fonctions < 50 lignes.

Règle user 2026-10-24, reprise par la spécification (ENF-12) : aucun fichier
ne dépasse 500 lignes, aucune fonction ne dépasse 50 lignes. Le garde est
exécuté par la CI (check `ci`) et par `make gardes`.

Périmètre : tout le dépôt sauf les chemins listés dans
`scripts/gardes/exceptions.txt` (motifs glob, un par ligne, `#` = commentaire).
Le pipeline CI imposé (`.github/`) et le cahier des charges verbatim
(`docs/spec/`) en font partie : ils ne sont pas du code du projet.

Usage : `python3 scripts/gardes/tailles.py [--racine .] [--json]`
Sortie : 0 si conforme, 1 sinon (liste des dépassements sur stdout).
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import sys

LIMITE_FICHIER = 500
LIMITE_FONCTION = 50
EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".html", ".htm", ".js", ".mjs",
              ".css", ".sh", ".json", ".txt", ".toml", ".cfg", ".ini"}
RACINES_EXCLUES = {".git", "__pycache__", ".pytest_cache", "node_modules",
                   ".venv", "venv", "build", "dist"}
CHEMIN_EXCEPTIONS = os.path.join("scripts", "gardes", "exceptions.txt")


def charger_exceptions(racine: str) -> list[str]:
    """Lit les motifs d'exclusion (absents → liste vide)."""
    chemin = os.path.join(racine, CHEMIN_EXCEPTIONS)
    if not os.path.isfile(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        lignes = [l.strip() for l in f]
    return [l for l in lignes if l and not l.startswith("#")]


def exclu(relatif: str, motifs: list[str]) -> bool:
    """Vrai si le chemin relatif tombe sous un motif d'exclusion."""
    for motif in motifs:
        if motif.endswith("/**"):
            if relatif.startswith(motif[:-3].rstrip("/") + "/"):
                return True
            continue
        if fnmatch.fnmatch(relatif, motif):
            return True
    return False


def iterer_fichiers(racine: str, motifs: list[str]):
    """Parcourt les fichiers du périmètre, dans l'ordre, en chemin relatif."""
    for chemin, dossiers, fichiers in os.walk(racine):
        dossiers[:] = sorted(d for d in dossiers if d not in RACINES_EXCLUES)
        for nom in sorted(fichiers):
            absolu = os.path.join(chemin, nom)
            relatif = os.path.relpath(absolu, racine)
            if os.path.splitext(nom)[1].lower() not in EXTENSIONS:
                continue
            if exclu(relatif, motifs):
                continue
            yield relatif, absolu


def compter_lignes(absolu: str) -> int:
    """Nombre de lignes d'un fichier texte (0 si illisible)."""
    try:
        with open(absolu, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeError):
        return 0


def fonctions_longues(absolu: str) -> list[tuple[str, int]]:
    """Fonctions Python dépassant la limite (nom, longueur)."""
    if not absolu.endswith(".py"):
        return []
    try:
        with open(absolu, encoding="utf-8") as f:
            arbre = ast.parse(f.read(), filename=absolu)
    except (OSError, UnicodeError, SyntaxError):
        return []
    longues = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        taille = (noeud.end_lineno or noeud.lineno) - noeud.lineno + 1
        if taille > LIMITE_FONCTION:
            longues.append((noeud.name, taille))
    return longues


def verifier(racine: str = ".") -> list[dict]:
    """Retourne la liste des dépassements (vide si le dépôt est conforme)."""
    motifs = charger_exceptions(racine)
    problemes: list[dict] = []
    for relatif, absolu in iterer_fichiers(racine, motifs):
        lignes = compter_lignes(absolu)
        if lignes > LIMITE_FICHIER:
            problemes.append({"fichier": relatif, "regle": "fichier",
                              "lignes": lignes, "limite": LIMITE_FICHIER})
        for nom, taille in fonctions_longues(absolu):
            problemes.append({"fichier": relatif, "regle": "fonction",
                              "fonction": nom, "lignes": taille,
                              "limite": LIMITE_FONCTION})
    return problemes


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI : 0 conforme, 1 dépassement(s)."""
    analyse = argparse.ArgumentParser(description=__doc__)
    analyse.add_argument("--racine", default=".")
    analyse.add_argument("--json", action="store_true")
    args = analyse.parse_args(argv)
    problemes = verifier(args.racine)
    if args.json:
        print(json.dumps(problemes, ensure_ascii=False, indent=2))
        return 1 if problemes else 0
    if not problemes:
        print("tailles: conforme (fichiers <= %d lignes, fonctions <= %d)"
              % (LIMITE_FICHIER, LIMITE_FONCTION))
        return 0
    for p in problemes:
        if p["regle"] == "fichier":
            print("::error file=%s::%d lignes (limite %d) — découper le fichier"
                  % (p["fichier"], p["lignes"], p["limite"]))
        else:
            print("::error file=%s::%s() fait %d lignes (limite %d)"
                  % (p["fichier"], p["fonction"], p["lignes"], p["limite"]))
    print("tailles: %d dépassement(s)" % len(problemes))
    return 1


if __name__ == "__main__":
    sys.exit(main())
