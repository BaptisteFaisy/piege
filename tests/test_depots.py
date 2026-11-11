"""Tests des règles transverses du contrat — lot 0.

C3 : le cœur n'a aucune dépendance tierce (bibliothèque standard uniquement,
imports AWS/LLM paresseux à l'intérieur des fonctions).
C6 : l'heure n'est lue que dans `piege.types`.
"""

from __future__ import annotations

import ast
import os
import sys
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "src", "piege")
STDLIB = set(sys.stdlib_module_names)
AUTORISES = {"piege"}


def fichiers_python(dossier):
    """Liste les fichiers `.py` d'un dossier, triés."""
    trouves = []
    for chemin, sous, fichiers in os.walk(dossier):
        sous[:] = sorted(s for s in sous if s != "__pycache__")
        for nom in sorted(fichiers):
            if nom.endswith(".py"):
                trouves.append(os.path.join(chemin, nom))
    return trouves


def arbre(chemin):
    """Parse un fichier Python ; None si illisible."""
    with open(chemin, encoding="utf-8") as f:
        return ast.parse(f.read(), filename=chemin)


def imports_tete(arbre_ast):
    """Noms importés au niveau module (hors fonctions)."""
    noms = []
    for noeud in arbre_ast.body:
        if isinstance(noeud, ast.Import):
            noms += [a.name.split(".")[0] for a in noeud.names]
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            noms.append(noeud.module.split(".")[0])
    return noms


class TestDependances(unittest.TestCase):
    """Aucune dépendance tierce au niveau module dans `src/piege`."""

    def test_imports_stdlib_uniquement(self):
        if not os.path.isdir(SOURCE):
            self.skipTest("src/piege absent")
        fautifs = []
        for chemin in fichiers_python(SOURCE):
            for nom in imports_tete(arbre(chemin)):
                if nom in STDLIB or nom in AUTORISES or nom == "__future__":
                    continue
                fautifs.append("%s importe %s en tête de module"
                               % (os.path.relpath(chemin, RACINE), nom))
        self.assertEqual(fautifs, [])


class TestHorloge(unittest.TestCase):
    """`datetime.now` n'apparaît que dans `piege.types` (C6/§6)."""

    def test_aucun_now_hors_types(self):
        if not os.path.isdir(SOURCE):
            self.skipTest("src/piege absent")
        autorises = {"types.py", "types_base.py"}
        fautifs = []
        for chemin in fichiers_python(SOURCE):
            if os.path.basename(chemin) in autorises:
                continue
            with open(chemin, encoding="utf-8") as f:
                source = f.read()
            if "datetime.now" in source or "time.time()" in source:
                fautifs.append(os.path.relpath(chemin, RACINE))
        self.assertEqual(fautifs, [])


class TestDocstrings(unittest.TestCase):
    """Chaque module du paquet porte une docstring (C7)."""

    def test_modules_documentes(self):
        if not os.path.isdir(SOURCE):
            self.skipTest("src/piege absent")
        sans = []
        for chemin in fichiers_python(SOURCE):
            if os.path.basename(chemin) == "__init__.py":
                continue
            if not ast.get_docstring(arbre(chemin)):
                sans.append(os.path.relpath(chemin, RACINE))
        self.assertEqual(sans, [])


if __name__ == "__main__":
    unittest.main()
