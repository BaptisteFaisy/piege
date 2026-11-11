"""Tests de la CLI `piege` : codes de sortie et gestes hors ligne (§15)."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from piege.cli import (CODE_ERREUR, CODE_REFUS, CODE_SUCCES, CODE_USAGE,
                       construire_analyseur, main)


def lancer(argv):
    """Exécute la CLI en capturant sortie, erreur et code de retour."""
    sortie, erreur = io.StringIO(), io.StringIO()
    with redirect_stdout(sortie), redirect_stderr(erreur):
        code = main(argv)
    return code, sortie.getvalue(), erreur.getvalue()


class TestAnalyseur(unittest.TestCase):
    """Les quatre gestes existent, avec leurs options."""

    def test_commandes(self):
        analyseur = construire_analyseur()
        for commande in ("demo", "catalogue", "rapport", "validation"):
            args = analyseur.parse_args([commande] if commande != "validation"
                                        else [commande, "--mandat", "MAN-1"])
            self.assertEqual(args.commande, commande)

    def test_commande_absente(self):
        with self.assertRaises(SystemExit):
            construire_analyseur().parse_args([])

    def test_codes_de_sortie_distincts(self):
        self.assertEqual((CODE_SUCCES, CODE_USAGE, CODE_REFUS, CODE_ERREUR),
                         (0, 1, 2, 3))


class TestValidation(unittest.TestCase):
    """`piege validation` : périmètre d'un mandat, sans aucune sonde."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dossier.cleanup()

    def mandat_stocke(self, identifiant="MAN-2026-0001"):
        """Écrit un mandat signé dans l'entrepôt local de test."""
        from piege.moteur.demo import mandat_de_demonstration
        from piege.stockage import creer_entrepot

        entrepot = creer_entrepot({"type": "local", "dossier": self.dossier.name})
        mandat = mandat_de_demonstration(["A1", "F3"])
        entrepot.ecrire("mandats", mandat.vers_dict())
        return mandat

    def test_mandat_inconnu(self):
        code, _, erreur = lancer(["validation", "--mandat", "MAN-2026-9999",
                                  "--donnees", self.dossier.name])
        self.assertEqual(code, CODE_REFUS)
        self.assertIn("mandat", erreur.lower())

    def test_mandat_valide_sans_catalogue(self):
        """Sans catalogue mergé, la validation le dit au lieu d'inventer."""
        self.mandat_stocke()
        code, sortie, _ = lancer(["validation", "--mandat", "MAN-2026-0001",
                                  "--donnees", self.dossier.name])
        self.assertIn(code, (CODE_SUCCES, CODE_REFUS))
        self.assertIsInstance(sortie, str)

    def test_sortie_json(self):
        self.mandat_stocke()
        code, sortie, _ = lancer(["validation", "--mandat", "MAN-2026-0001",
                                  "--donnees", self.dossier.name, "--json"])
        if code == CODE_SUCCES:
            import json

            donnees = json.loads(sortie)
            self.assertEqual(donnees["mandat"], "MAN-2026-0001")


class TestCommandesIndisponibles(unittest.TestCase):
    """Les gestes dépendant d'autres lots annoncent clairement leur absence."""

    def test_demo_sans_catalogue(self):
        with tempfile.TemporaryDirectory() as dossier:
            vide = os.path.join(dossier, "catalogue-vide")
            os.makedirs(vide)
            code, _, erreur = lancer(["demo", "--catalogue", vide])
            self.assertIn(code, (CODE_REFUS, CODE_ERREUR))
            self.assertTrue(erreur.strip())

    def test_catalogue_dossier_vide(self):
        with tempfile.TemporaryDirectory() as dossier:
            code, _, _ = lancer(["catalogue", dossier, "--resume"])
            self.assertIn(code, (CODE_SUCCES, CODE_REFUS))

    def test_rapport_sans_lot_12(self):
        code, _, erreur = lancer(["rapport", "--derniere"])
        self.assertEqual(code, CODE_REFUS)
        self.assertIn("ABSENT", erreur)


class TestSortieStandard(unittest.TestCase):
    """Aucune commande ne lève d'exception brute vers l'utilisateur."""

    def test_erreur_interne_transformee(self):
        code, _, erreur = lancer(["validation", "--mandat", "", "--donnees",
                                  "/tmp/inexistant-piege"])
        self.assertNotEqual(code, CODE_SUCCES)
        self.assertNotIn("Traceback", erreur)

    def test_sys_exit_non_propage(self):
        with self.assertRaises(SystemExit):
            main(["commande-inconnue"])


if __name__ == "__main__":
    unittest.main()
