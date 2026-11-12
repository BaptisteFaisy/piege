"""Tests du mode « réponse gratuite » (scripts/demo-libre.py).

Le script n'est pas exécuté en CI (il appelle un fournisseur réel) : on vérifie
ici qu'il est importable, qu'il ne déclenche aucun réseau à l'import, que la
narration annonce 0 €, et que la cible réelle accepte un endpoint libre
(sans clé) quand l'URL est explicite.
"""

from __future__ import annotations

import importlib.util
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, "scripts", "demo-libre.py")


def charger():
    specification = importlib.util.spec_from_file_location("demo_libre", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


demo_libre = charger()


class TestReponseLibre(unittest.TestCase):
    """Le fournisseur libre est un client OpenAI-compatible, sans clé."""

    def test_fournisseur_libre_sans_cle(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        fournisseur = demo_libre.fournisseur(sans_cle=True)
        self.assertIsInstance(fournisseur, FournisseurInferhub)
        self.assertEqual(fournisseur.cle, "")

    def test_messages_naifs(self):
        messages = demo_libre.messages()
        self.assertIn("assistant RH", messages[0]["content"])
        self.assertIn("32 400", messages[1]["content"])

    def test_narration_annonce_zero_euro(self):
        narration = demo_libre.narrer({"texte": "32 400 EUR", "modele": "openai",
                                       "latence_ms": 10, "essais": 1},
                                      "https://text.pollinations.ai/openai")
        self.assertIn("0 €", narration)
        self.assertIn("32 400", narration)

    def test_import_sans_reseau(self):
        """L'import du script ne doit ouvrir aucune connexion."""
        with open(SCRIPT, encoding="utf-8") as f:
            source = f.read()
        for interdit in ("urllib.request", "requests.", "http.client",
                         "socket.create_connection"):
            self.assertNotIn(interdit, source)


class TestCibleReelleSansCle(unittest.TestCase):
    """Une URL libre explicite vaut autorisation : pas besoin de clé."""

    def test_url_libre_sans_cle_acceptee(self):
        from piege.cibles.inferhub import CibleInferhub

        anciennes = {}
        for var in ("PIEGE_LLM_URL", "PIEGE_LLM_CLE"):
            anciennes[var] = os.environ.pop(var, None)
        os.environ["PIEGE_LLM_URL"] = "https://text.pollinations.ai/openai"
        try:
            cible = CibleInferhub({"modele": "openai", "corpus": "demo/corpus"})
            fournisseur = cible.fournisseur
            self.assertEqual(fournisseur.cle, "sans-cle")
            self.assertIn("text.pollinations", fournisseur.url)
        finally:
            os.environ.pop("PIEGE_LLM_URL", None)
            for var, valeur in anciennes.items():
                if valeur is not None:
                    os.environ[var] = valeur

    def test_sans_cle_ni_url_refusee(self):
        from piege.cibles.inferhub import CibleInferhub

        anciennes = {var: os.environ.pop(var, None)
                     for var in ("PIEGE_LLM_URL", "PIEGE_LLM_CLE")}
        try:
            with self.assertRaises(ValueError):
                CibleInferhub({"modele": "openai"}).fournisseur
        finally:
            for var, valeur in anciennes.items():
                if valeur is not None:
                    os.environ[var] = valeur


if __name__ == "__main__":
    unittest.main()