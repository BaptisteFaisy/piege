#!/usr/bin/env python3
"""Lanceur de tests sans dépendance tierce (repli de pytest).

`make test` utilise pytest quand il est installé ; ce lanceur prend le relais
sinon (machine nue, conteneur de juge). Il découvre `tests/test_*.py`, exécute
les fonctions `test_*` et les `unittest.TestCase`, et rend 0 si tout passe.

Usage : `python3 scripts/lance_tests.py [tests]`
"""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "src")


def preparer_pythonpath() -> None:
    """Place `src/` et la racine en tête de PYTHONPATH."""
    for chemin in (SOURCE, RACINE):
        if chemin not in sys.path:
            sys.path.insert(0, chemin)


def charger(module_path: str):
    """Importe un fichier de test comme module isolé."""
    nom = os.path.splitext(os.path.basename(module_path))[0]
    spec = importlib.util.spec_from_file_location(nom, module_path)
    if spec is None or spec.loader is None:
        raise ImportError("spec illisible pour %s" % module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


def decouvrir(dossier: str) -> list[str]:
    """Liste les fichiers de test, triés."""
    if os.path.isfile(dossier):
        return [dossier]
    trouves = []
    for chemin, sous, fichiers in os.walk(dossier):
        sous.sort()
        for nom in sorted(fichiers):
            if nom.startswith("test_") and nom.endswith(".py"):
                trouves.append(os.path.join(chemin, nom))
    return trouves


def collecter(module) -> list:
    """Fonctions `test_*` et classes `unittest.TestCase` d'un module."""
    cibles = []
    for nom in sorted(dir(module)):
        objet = getattr(module, nom)
        if nom.startswith("test_") and callable(objet):
            cibles.append((nom, objet))
        elif isinstance(objet, type) and issubclass(objet, unittest.TestCase):
            cibles.append((nom, objet))
    return cibles


def executer(cible) -> list[str]:
    """Exécute une cible ; retourne la liste des erreurs (vide si succès)."""
    nom, objet = cible
    if isinstance(objet, type):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(objet)
        resultat = unittest.TextTestRunner(stream=open(os.devnull, "w"),
                                           verbosity=0).run(suite)
        erreurs = []
        for _, trace in list(resultat.failures) + list(resultat.errors):
            erreurs.append("%s : %s" % (nom, trace.strip().splitlines()[-1]))
        return erreurs
    try:
        objet()
        return []
    except Exception:                                   # noqa: BLE001
        return ["%s : %s" % (nom, traceback.format_exc(limit=3).strip())]


def main(argv: list[str]) -> int:
    """Exécute la découverte ; 0 si tout passe."""
    preparer_pythonpath()
    dossier = argv[0] if argv else os.path.join(RACINE, "tests")
    total, echecs = 0, []
    for fichier in decouvrir(dossier):
        try:
            module = charger(fichier)
        except Exception:                               # noqa: BLE001
            echecs.append("%s : import impossible\n%s" % (fichier, traceback.format_exc(limit=3)))
            continue
        for cible in collecter(module):
            total += 1
            for erreur in executer(cible):
                echecs.append("%s → %s" % (os.path.relpath(fichier, RACINE), erreur))
    for erreur in echecs:
        print("ECHEC %s" % erreur)
    print("lanceur stdlib : %d test(s), %d échec(s)" % (total, len(echecs)))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
