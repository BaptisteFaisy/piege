"""Tests du portail statique : chaîne de preuves exposée, fichiers scindés.

Le portail n'a pas d'étape de construction (test_portail_livre l'atteste) ; il
doit afficher la chaîne de preuves d'une campagne (une trace vérifiable par
étape) sans dépasser la garde de taille des fichiers.
"""

from __future__ import annotations

import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTAL = os.path.join(RACINE, "portal")


def lire(nom: str) -> str:
    with open(os.path.join(PORTAL, nom), encoding="utf-8") as f:
        return f.read()


class TestPortailPreuves(unittest.TestCase):
    """La chaîne de preuves est un onglet à part entière du portail."""

    def test_onglet_present(self):
        index = lire("index.html")
        self.assertIn('data-onglet="preuves"', index)
        self.assertIn('id="onglet-preuves"', index)
        self.assertIn('id="btn-preuves"', index)

    def test_chargeur_appelle_la_route_du_rapport(self):
        app = lire("app.js")
        self.assertIn("chargerPreuves", app)
        self.assertIn("preuves", app)
        self.assertIn("/rapports/", app)

    def test_fichiers_scindes_sous_la_limite(self):
        """app.js et evo.js restent chacun sous 500 lignes (garde de taille)."""
        for nom in ("app.js", "evo.js", "index.html", "styles.css"):
            self.assertLessEqual(lire(nom).count("\n") + 1, 500,
                                 "%s dépasse 500 lignes" % nom)

    def test_evo_charge_apres_app(self):
        index = lire("index.html")
        position_app = index.index('src="app.js"')
        position_evo = index.index('src="evo.js"')
        self.assertLess(position_app, position_evo,
                        "evo.js doit être chargé après app.js")


if __name__ == "__main__":
    unittest.main()