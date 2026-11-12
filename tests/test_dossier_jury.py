"""Tests du dossier jury (`make jury`).

Le dossier est ce que le jury ouvre : il doit être produit sans réseau, sans
modèle et sans coût, et chaque pièce doit prouver quelque chose — dont la
boucle de correction complète (ouverture → accord → application → rejeu →
preuve de fermeture datée).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, "scripts", "jury", "dossier.py")

PIECES = ("INDEX.md", "campagne.json", "rapport-fr.md", "rapport-en.md",
          "attestation.md", "cloture.md", "recettes.md", "tracabilite.md",
          "evaluation.json", "preuves.json")


def _lire(chemin: str) -> str:
    with open(chemin, encoding="utf-8") as f:
        return f.read()


class TestDossierJudge(unittest.TestCase):
    """Un dossier complet, reproductible et démontratif."""

    @classmethod
    def setUpClass(cls):
        cls._dossier = tempfile.TemporaryDirectory()
        cls.sortie = os.path.join(cls._dossier.name, "dossier")
        resultat = subprocess.run(
            [sys.executable, SCRIPT, cls.sortie], capture_output=True, text=True,
            cwd=RACINE, timeout=900,
            env=dict(os.environ, PYTHONPATH=os.path.join(RACINE, "src")))
        cls.code = resultat.returncode
        cls.sortie_texte = resultat.stdout + resultat.stderr

    @classmethod
    def tearDownClass(cls):
        cls._dossier.cleanup()

    def test_commande_reussie(self):
        self.assertEqual(self.code, 0, self.sortie_texte)

    def test_toutes_les_pieces_sont_la(self):
        for nom in PIECES:
            self.assertTrue(os.path.isfile(os.path.join(self.sortie, nom)),
                            "pièce manquante : %s" % nom)

    def test_cloture_prouvee(self):
        """La boucle de correction se termine par une fermeture prouvée."""
        texte = _lire(os.path.join(self.sortie, "cloture.md"))
        self.assertIn("ferme", texte)
        self.assertIn("sha256:", texte)
        self.assertIn("Rejeu de l'attaque d'origine", texte)

    def test_recettes_toutes_prouvees(self):
        texte = _lire(os.path.join(self.sortie, "recettes.md"))
        self.assertIn("prouve", texte)
        self.assertNotIn("a_prouver", texte)

    def test_evaluation_conforme(self):
        donnees = json.loads(_lire(os.path.join(self.sortie, "evaluation.json")))
        self.assertTrue(donnees["conforme"])

    def test_preuves_non_vides(self):
        preuves = json.loads(_lire(os.path.join(self.sortie, "preuves.json")))
        self.assertTrue(preuves)
        for element in preuves:
            self.assertTrue(element["empreinte"].startswith("sha256:"))

    def test_index_despiece_les_pieces(self):
        index = _lire(os.path.join(self.sortie, "INDEX.md"))
        for nom in ("cloture.md", "recettes.md", "evaluation.json"):
            self.assertIn(nom, index)


if __name__ == "__main__":
    unittest.main()