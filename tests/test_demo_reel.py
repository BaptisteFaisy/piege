"""Tests de la démo réelle rejouée (0 €).

La campagne réelle enregistrée doit être rejouable **sans appel, sans clé et
sans réseau**, et le magasin qu'elle alimente doit produire le même rapport
que la campagne d'origine : c'est la démonstration « vraie » qui ne coûte rien.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(RACINE, "demo", "reel", "campagne-reelle.json")
SCRIPT = os.path.join(RACINE, "scripts", "jury", "demo-reel.py")

MOTIF_SECRET = re.compile(r"sk-[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,}"
                          r"|PIEGE_LLM_CLE\s*[=:]\s*\S+")


class TestFixtureReelle(unittest.TestCase):
    """La fixture est complète, sourcée et sans secret."""

    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_campagne_et_executions(self):
        self.assertEqual(len(self.fixture["campagnes"]), 1)
        self.assertGreaterEqual(len(self.fixture["executions"]), 3)

    def test_une_decouverte_confirmee(self):
        self.assertTrue(self.fixture["findings"])

    def test_cout_reel_mesure(self):
        """La fixture porte le coût réel mesuré à l'enregistrement."""
        campagne = list(self.fixture["campagnes"].values())[0]
        self.assertGreater(campagne["cout_mesure"], 0)

    def test_source_declaree(self):
        source = self.fixture["source"]
        self.assertIn("cible", source)
        self.assertIn("juge", source)
        self.assertTrue(source["enregistree_le"])

    def test_aucun_secret_dans_la_fixture(self):
        with open(FIXTURE, encoding="utf-8") as f:
            brut = f.read()
        self.assertIsNone(MOTIF_SECRET.search(brut),
                          "la fixture contient un secret")


class TestRejeuGratuit(unittest.TestCase):
    """Le rejeu n'ouvre aucune connexion et produit la narration."""

    def test_le_script_ne_fait_aucun_appel_reseau(self):
        with open(SCRIPT, encoding="utf-8") as f:
            source = f.read()
        for interdit in ("urllib.request", "http.client", "requests.",
                         "socket.create_connection"):
            self.assertNotIn(interdit, source,
                              "le rejeu ne doit pas ouvrir de connexion")

    def test_rejeu_ecrit_le_magasin_et_la_narration(self):
        with tempfile.TemporaryDirectory() as dossier:
            magasin = os.path.join(dossier, "magasin")
            narration = os.path.join(dossier, "demo-reel.md")
            resultat = subprocess.run(
                [sys.executable, SCRIPT, "--magasin", magasin,
                 "--sortie", narration],
                capture_output=True, text=True, cwd=RACINE, timeout=300,
                env=dict(os.environ, PYTHONPATH=os.path.join(RACINE, "src")))
            self.assertEqual(resultat.returncode, 0, resultat.stderr)
            self.assertTrue(os.path.isfile(narration))
            with open(narration, encoding="utf-8") as f:
                texte = f.read()
            self.assertIn("0 €", texte)
            self.assertIn("REUSSI", texte)
            for table in ("campagnes", "executions", "findings"):
                self.assertTrue(os.path.isfile(os.path.join(magasin, "%s.json" % table)))

    def test_le_magasin_produit_le_rapport(self):
        """La campagne rejouée donne un rapport : le portail peut la servir."""
        from piege.rapport.rapport import rapport_depuis_entrepot
        from piege.stockage import creer_entrepot

        with tempfile.TemporaryDirectory() as dossier:
            magasin = os.path.join(dossier, "magasin")
            subprocess.run([sys.executable, SCRIPT, "--magasin", magasin,
                            "--sortie", os.path.join(dossier, "n.md")],
                           capture_output=True, text=True, cwd=RACINE, timeout=300,
                           env=dict(os.environ,
                                    PYTHONPATH=os.path.join(RACINE, "src")))
            entrepot = creer_entrepot({"type": "local", "dossier": magasin})
            campagnes = entrepot.lister("campagnes")
            self.assertTrue(campagnes)
            identifiant = campagnes[0]["id"]
            rapport = rapport_depuis_entrepot(entrepot, identifiant,
                                              campagnes[0]["tenant_id"], "fr")
            self.assertIn("Synthèse", rapport)


if __name__ == "__main__":
    unittest.main()