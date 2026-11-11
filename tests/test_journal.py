"""Tests du journal chaîné : immuabilité, détection d'altération, marqueurs."""

from __future__ import annotations

import unittest

from piege.securite.journal import (EMPREEINTE_GENESIS, Journal, entree_journal,
                                    verifier_ligne)
from piege.types import Decision, fixer_horloge

INSTANT = "2026-11-24T09:14:03Z"


class TestChaine(unittest.TestCase):
    """Le journal est append-only et chaîné par empreinte (§19.2)."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self.journal = Journal()

    def tearDown(self):
        fixer_horloge(None)

    def test_premiere_ligne_sur_genese(self):
        ligne = self.journal.consigner("moteur", "sonde", "TEN-acme")
        self.assertEqual(ligne["empreinte_precedente"], EMPREEINTE_GENESIS)
        self.assertTrue(ligne["empreinte"].startswith("sha256:"))

    def test_chainage(self):
        premiere = self.journal.consigner("moteur", "sonde", "TEN-acme")
        seconde = self.journal.consigner("moteur", "reponse", "TEN-acme")
        self.assertEqual(seconde["empreinte_precedente"], premiere["empreinte"])
        self.assertTrue(self.journal.verifier_chaine())

    def test_alteration_detectee(self):
        self.journal.consigner("moteur", "sonde", "TEN-acme")
        self.journal.consigner("moteur", "reponse", "TEN-acme")
        self.journal._lignes[0]["quoi"] = "sonde-modifiee"
        self.assertFalse(self.journal.verifier_chaine())

    def test_suppression_detectee(self):
        for quoi in ("sonde", "reponse", "verdict"):
            self.journal.consigner("moteur", quoi, "TEN-acme")
        del self.journal._lignes[1]
        self.assertFalse(self.journal.verifier_chaine())

    def test_copie_exterieure_non_modifiable(self):
        self.journal.consigner("moteur", "sonde", "TEN-acme")
        copie = self.journal.lignes()
        copie[0]["quoi"] = "autre"
        self.assertTrue(self.journal.verifier_chaine())

    def test_verifieur_de_ligne_isolee(self):
        ligne = entree_journal("moteur", "sonde", "TEN-acme")
        self.assertTrue(verifier_ligne(ligne))
        ligne["tenant"] = "TEN-autre"
        self.assertFalse(verifier_ligne(ligne))


class TestContenu(unittest.TestCase):
    """Marqueur sonde de test, décisions de Policy, flux de refus."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self.journal = Journal()

    def tearDown(self):
        fixer_horloge(None)

    def test_marqueur_sonde_de_test(self):
        ligne = self.journal.consigner("moteur", "sonde", "TEN-acme")
        self.assertEqual(ligne["marqueur"], "sonde_de_test")

    def test_marqueur_trafic_reel(self):
        ligne = self.journal.consigner("moteur", "sonde", "TEN-acme",
                                       sonde_de_test=False)
        self.assertEqual(ligne["marqueur"], "trafic_reel")

    def test_details_enregistres(self):
        ligne = self.journal.consigner("moteur", "sonde", "TEN-acme",
                                       {"technique": "A1", "tour": 1})
        self.assertEqual(ligne["details"]["technique"], "A1")

    def test_decision_autorisee(self):
        accord = Decision(accorde=True, regle="autorise", motif="ok",
                          outil="Cible___sonde")
        ligne = self.journal.consigner_decision(accord, "TEN-acme")
        self.assertEqual(ligne["quoi"], "autorise")
        self.assertEqual(self.journal.refus(), [])

    def test_decision_refusee(self):
        refus = Decision(accorde=False, regle="perimetre.application",
                         motif="cible hors mandat", outil="Cible___sonde",
                         code="hors_perimetre")
        ligne = self.journal.consigner_decision(refus, "TEN-acme")
        self.assertEqual(ligne["quoi"], "refus")
        self.assertEqual(len(self.journal.refus()), 1)
        self.assertEqual(self.journal.refus()[0]["details"]["code"],
                         "hors_perimetre")

    def test_ecriture_deleguee_a_lentrepot(self):
        recus = []
        journal = Journal(ecrire=recus.append)
        journal.consigner("moteur", "sonde", "TEN-acme")
        self.assertEqual(len(recus), 1)
        self.assertEqual(recus[0]["quoi"], "sonde")


if __name__ == "__main__":
    unittest.main()
