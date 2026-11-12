"""Tests du reconstructeur du site (scripts/jury/site.py).

L'état du site est reproductible : une campagne réelle rejouée, une découverte
fermée par la boucle complète avec une preuve de fermeture datée. Ces tests
vérifient que le script produit cet état, hors ligne et sans appel.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, "scripts", "jury", "site.py")


class TestSiteReconstruit(unittest.TestCase):
    """Le script régénère l'état complet du site."""

    @classmethod
    def setUpClass(cls):
        cls._dossier = tempfile.TemporaryDirectory()
        cls.magasin = os.path.join(cls._dossier.name, "site")
        resultat = subprocess.run(
            [sys.executable, SCRIPT, "--magasin", cls.magasin],
            capture_output=True, text=True, cwd=RACINE, timeout=900,
            env=dict(os.environ, PYTHONPATH=os.path.join(RACINE, "src")))
        cls.code = resultat.returncode
        cls.sortie = resultat.stdout + resultat.stderr

    @classmethod
    def tearDownClass(cls):
        cls._dossier.cleanup()

    def test_commande_reussie(self):
        self.assertEqual(self.code, 0, self.sortie)

    def test_campagne_reelle_presente(self):
        campagnes = json.load(open(os.path.join(self.magasin, "campagnes.json"),
                                   encoding="utf-8"))
        campagne = list(campagnes.values())[0]
        self.assertEqual(campagne["id"], "CMP-1113")
        self.assertGreater(campagne["cout_mesure"], 0)

    def test_decouverte_fermee_avec_preuve(self):
        findings = json.load(open(os.path.join(self.magasin, "findings.json"),
                                  encoding="utf-8"))
        finding = next(iter(findings.values()))
        self.assertEqual(finding["statut"], "ferme")
        self.assertTrue(finding.get("preuve_fermeture_ids"))
        self.assertTrue(finding.get("correctif_ids"))

    def test_preuve_de_fermeture_datée(self):
        preuves = json.load(open(os.path.join(self.magasin, "preuves.json"),
                                 encoding="utf-8"))
        preuve = next(iter(preuves.values()))
        self.assertTrue(preuve["empreinte"].startswith("sha256:"))
        self.assertTrue(preuve["date"])

    def test_aucun_secret_ni_donnee_reelle(self):
        """Le magasin ne contient ni secret ni donnée personnelle réelle."""
        for table in ("campagnes", "executions", "findings", "preuves"):
            brut = open(os.path.join(self.magasin, "%s.json" % table),
                        encoding="utf-8").read()
            for interdit in ("sk-live", "ghp_", "PIEGE_LLM_CLE"):
                self.assertNotIn(interdit, brut)
        findings = json.load(open(os.path.join(self.magasin, "findings.json"),
                                  encoding="utf-8"))
        finding = next(iter(findings.values()))
        self.assertIn("C4", finding["technique_ids"])


if __name__ == "__main__":
    unittest.main()