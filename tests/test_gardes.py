"""Tests du garde de taille (ENF-12, règle C1) — lot 0."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GARDE = os.path.join(RACINE, "scripts", "gardes", "tailles.py")


def charger_garde():
    """Importe `scripts/gardes/tailles.py` comme module isolé."""
    spec = importlib.util.spec_from_file_location("tailles", GARDE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tailles = charger_garde()


class TestGarde(unittest.TestCase):
    """Détection des fichiers et fonctions trop longs."""

    def ecrire(self, dossier, nom, contenu):
        chemin = os.path.join(dossier, nom)
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(contenu)
        return chemin

    def test_fichier_conforme(self):
        with tempfile.TemporaryDirectory() as dossier:
            self.ecrire(dossier, "src/ok.py", "x = 1\n" * 10)
            self.assertEqual(tailles.verifier(dossier), [])

    def test_fichier_trop_long(self):
        with tempfile.TemporaryDirectory() as dossier:
            self.ecrire(dossier, "src/long.py", "x = 1\n" * 501)
            problemes = tailles.verifier(dossier)
            self.assertEqual(len(problemes), 1)
            self.assertEqual(problemes[0]["regle"], "fichier")
            self.assertEqual(problemes[0]["lignes"], 501)

    def test_fonction_trop_longue(self):
        corps = "".join("    x%d = %d\n" % (i, i) for i in range(55))
        with tempfile.TemporaryDirectory() as dossier:
            self.ecrire(dossier, "src/f.py", "def grande():\n" + corps)
            problemes = tailles.verifier(dossier)
            self.assertEqual([p["regle"] for p in problemes], ["fonction"])
            self.assertEqual(problemes[0]["fonction"], "grande")

    def test_limite_exacte_acceptee(self):
        with tempfile.TemporaryDirectory() as dossier:
            self.ecrire(dossier, "src/limite.py", "x = 1\n" * 500)
            self.assertEqual(tailles.verifier(dossier), [])

    def test_exceptions_respectees(self):
        with tempfile.TemporaryDirectory() as dossier:
            self.ecrire(dossier, "scripts/gardes/exceptions.txt", ".github/**\n")
            self.ecrire(dossier, ".github/workflows/geant.yml", "a: 1\n" * 900)
            self.ecrire(dossier, "src/petit.py", "x = 1\n")
            self.assertEqual(tailles.verifier(dossier), [])

    def test_dossiers_ignores(self):
        with tempfile.TemporaryDirectory() as dossier:
            self.ecrire(dossier, ".git/config.py", "x = 1\n" * 900)
            self.ecrire(dossier, "__pycache__/x.py", "x = 1\n" * 900)
            self.assertEqual(tailles.verifier(dossier), [])

    def test_motif_exclu(self):
        self.assertTrue(tailles.exclu("docs/spec/a.md", ["docs/spec/**"]))
        self.assertTrue(tailles.exclu(".github/workflows/x.yml", [".github/**"]))
        self.assertFalse(tailles.exclu("src/piege/types.py", ["docs/spec/**"]))


class TestDepotConforme(unittest.TestCase):
    """Le dépôt lui-même respecte le garde (auto-contrôle continu)."""

    def test_aucun_depassement(self):
        problemes = tailles.verifier(RACINE)
        self.assertEqual(
            problemes, [],
            "dépassement(s) de taille : %s" % problemes[:5])


if __name__ == "__main__":
    unittest.main()
