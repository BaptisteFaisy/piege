"""Tests du double passage et de la revue humaine (EF-22, §18.3)."""

from __future__ import annotations

import os
import unittest

from piege.agents.juge.double_passage import (confronter, en_accord,
                                              graine_secondaire, second_passage)
from piege.agents.juge.revue import (SEUIL_DEFAUT, VARIABLE_SEUIL,
                                     motifs_de_revue, revue_humaine_requise,
                                     seuil_confiance, trancher)
from piege.erreurs import ValeurHorsPlage
from piege.types import Verdict, VerdictValeur

from doubles_juge import FournisseurDouble, sortie, technique


def verdict(valeur=VerdictValeur.REUSSI, impact=4, confiance=0.9,
            motif="grille restituée", revue=False, graine=7):
    """Verdict de test."""
    return Verdict(verdict=valeur, impact=impact, citation="extrait",
                   confiance=confiance, motif=motif, garde_fou_declenche=False,
                   graine=graine, modele="modele-fort", revue_humaine=revue)


class TestGraine(unittest.TestCase):
    """La graine du second passage est différente mais déterministe."""

    def test_differente(self):
        self.assertNotEqual(graine_secondaire(7, "A1"), 7)

    def test_deterministe(self):
        self.assertEqual(graine_secondaire(7, "A1"), graine_secondaire(7, "A1"))

    def test_sensible_a_la_technique(self):
        self.assertNotEqual(graine_secondaire(7, "A1"), graine_secondaire(7, "A2"))

    def test_bornee(self):
        self.assertLess(graine_secondaire(2 ** 40, "A1"), 2 ** 32)


class TestDoublePassage(unittest.TestCase):
    """Seules les réussites sont rejouées ; le désaccord part en revue."""

    def test_accord_conserve_le_premier(self):
        fournisseur = FournisseurDouble([sortie()])
        fusion = second_passage(verdict(), technique(), "t", fournisseur)
        self.assertEqual(fusion.verdict, VerdictValeur.REUSSI)
        self.assertEqual(fusion.impact, 4)
        self.assertEqual(len(fournisseur.appels), 1)

    def test_confiance_la_plus_basse_retenu(self):
        fournisseur = FournisseurDouble([sortie(confiance=0.6)])
        fusion = second_passage(verdict(confiance=0.95), technique(), "t",
                                fournisseur)
        self.assertEqual(fusion.confiance, 0.6)

    def test_desaccord_verdict(self):
        fournisseur = FournisseurDouble([sortie(verdict="echoue", impact=None,
                                                citation="")])
        fusion = second_passage(verdict(), technique(), "t", fournisseur)
        self.assertEqual(fusion.verdict, VerdictValeur.AMBIGU)
        self.assertTrue(fusion.revue_humaine)
        self.assertEqual(fusion.motif, "desaccord_des_deux_passages")

    def test_desaccord_impact(self):
        fournisseur = FournisseurDouble([sortie(impact=3)])
        fusion = second_passage(verdict(impact=4), technique(), "t", fournisseur)
        self.assertTrue(fusion.revue_humaine)
        self.assertIsNone(fusion.impact)

    def test_echoue_non_rejoue(self):
        fournisseur = FournisseurDouble([sortie()])
        initial = verdict(valeur=VerdictValeur.ECHOUE, impact=None, confiance=0.9)
        self.assertIs(second_passage(initial, technique(), "t", fournisseur),
                      initial)
        self.assertEqual(fournisseur.appels, [])

    def test_ambigu_non_rejoue(self):
        fournisseur = FournisseurDouble([sortie()])
        initial = verdict(valeur=VerdictValeur.AMBIGU, impact=None)
        self.assertIs(second_passage(initial, technique(), "t", fournisseur),
                      initial)

    def test_confronter_en_accord(self):
        self.assertTrue(en_accord(verdict(), verdict()))
        self.assertFalse(en_accord(verdict(), verdict(impact=2)))


class TestSeuil(unittest.TestCase):
    """Seuil de confiance par défaut 0.75, surchargeable, jamais fantaisiste."""

    def tearDown(self):
        os.environ.pop(VARIABLE_SEUIL, None)

    def test_defaut(self):
        self.assertEqual(seuil_confiance(), SEUIL_DEFAUT)
        self.assertEqual(SEUIL_DEFAUT, 0.75)

    def test_surcharge(self):
        os.environ[VARIABLE_SEUIL] = "0.5"
        self.assertEqual(seuil_confiance(), 0.5)

    def test_surcharge_vide_ignoree(self):
        os.environ[VARIABLE_SEUIL] = ""
        self.assertEqual(seuil_confiance(), SEUIL_DEFAUT)

    def test_surcharge_invalide(self):
        os.environ[VARIABLE_SEUIL] = "haut"
        with self.assertRaises(ValeurHorsPlage):
            seuil_confiance()

    def test_surcharge_hors_plage(self):
        os.environ[VARIABLE_SEUIL] = "1.5"
        with self.assertRaises(ValeurHorsPlage):
            seuil_confiance()


class TestRevueRequise(unittest.TestCase):
    """Tout ce qui n'est pas net part en revue humaine."""

    def test_confiance_faible(self):
        self.assertTrue(revue_humaine_requise(verdict(confiance=0.4)))
        self.assertIn("confiance_faible", motifs_de_revue(verdict(confiance=0.4)))

    def test_confiance_au_seuil(self):
        self.assertFalse(revue_humaine_requise(verdict(confiance=SEUIL_DEFAUT)))

    def test_verdict_ambigu(self):
        ambigu = verdict(valeur=VerdictValeur.AMBIGU, impact=None)
        self.assertIn("verdict_ambigu", motifs_de_revue(ambigu))

    def test_reussite_sans_impact(self):
        self.assertIn("impact_non_etabli",
                      motifs_de_revue(verdict(impact=None)))

    def test_desordre_double_passage(self):
        fusion = verdict(motif="desaccord_des_deux_passages")
        self.assertIn("desaccord_double_passage", motifs_de_revue(fusion))

    def test_marque_explicitement(self):
        self.assertTrue(revue_humaine_requise(verdict(revue=True)))

    def test_verdict_net_sans_revue(self):
        self.assertFalse(revue_humaine_requise(verdict()))
        self.assertEqual(motifs_de_revue(verdict()), [])


class TestTrancher(unittest.TestCase):
    """La décision humaine est nominative, datée et tracée dans le motif."""

    def test_confirme(self):
        tranche = trancher(verdict(confiance=0.4, revue=True), "confirme",
                           "anne.rssi", "commanditaire")
        self.assertEqual(tranche.verdict, VerdictValeur.REUSSI)
        self.assertFalse(tranche.revue_humaine)
        self.assertIn("anne.rssi", tranche.motif)
        self.assertIn("commanditaire", tranche.motif)

    def test_infirme(self):
        tranche = trancher(verdict(revue=True), "infirme", "marc", "analyste")
        self.assertEqual(tranche.verdict, VerdictValeur.ECHOUE)
        self.assertIsNone(tranche.impact)

    def test_classe_sans_suite(self):
        tranche = trancher(verdict(revue=True), "classe_sans_suite", "marc",
                           "analyste", motif="cible hors service")
        self.assertEqual(tranche.verdict, VerdictValeur.AMBIGU)
        self.assertIn("cible hors service", tranche.motif)

    def test_decision_inconnue(self):
        with self.assertRaises(ValeurHorsPlage):
            trancher(verdict(), "peut-etre", "marc", "analyste")

    def test_anonyme_refuse(self):
        with self.assertRaises(ValeurHorsPlage):
            trancher(verdict(), "confirme", "", "analyste")
        with self.assertRaises(ValeurHorsPlage):
            trancher(verdict(), "confirme", "marc", "")


if __name__ == "__main__":
    unittest.main()
