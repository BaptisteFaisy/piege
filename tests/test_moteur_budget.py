"""Tests du budget : compteur thread-safe et arrêt propre au seuil (R3)."""

from __future__ import annotations

import threading
import unittest

from piege.moteur import ConfigurationCampagne, executer_campagne
from piege.moteur.budget import CompteurBudget
from piege.types import StatutCampagne, fixer_horloge

from doubles import application, mandat, technique
from doubles_moteur import (CibleDouble, EntrepotDouble, JournalDouble,
                            juge_double)

INSTANT = "2026-11-24T09:14:03Z"


def config(**remplacements) -> ConfigurationCampagne:
    """Configuration hors ligne avec trois techniques dans le périmètre."""
    valeurs = dict(mandat=mandat(perimetre_techniques=["A1", "F3", "C1"]),
                   application=application(), cible=CibleDouble(),
                   techniques=[technique(id="A1"), technique(id="F3"),
                               technique(id="C1")],
                   graine=20261124, parallelisme=1, juge=juge_double(),
                   journal=JournalDouble(), entrepot=EntrepotDouble())
    valeurs.update(remplacements)
    return ConfigurationCampagne(**valeurs)


class TestCompteur(unittest.TestCase):
    """Compteur : consommation, reste, épuisement, concurrence."""

    def test_consommation(self):
        budget = CompteurBudget(appels_max=10, jetons_max=1000)
        self.assertTrue(budget.consommer(1, 100))
        self.assertEqual(budget.appels_consommes, 1)
        self.assertEqual(budget.jetons_consommes, 100)

    def test_restes(self):
        budget = CompteurBudget(appels_max=10, jetons_max=1000)
        budget.consommer(4, 250)
        self.assertEqual(budget.appels_restants(), 6)
        self.assertEqual(budget.jetons_restants(), 750)

    def test_refus_sans_consommation(self):
        budget = CompteurBudget(appels_max=2)
        budget.consommer(2)
        self.assertFalse(budget.consommer(1))
        self.assertEqual(budget.appels_consommes, 2)

    def test_refus_partiel(self):
        """Un appel possible mais pas les jetons : rien n'est consommé."""
        budget = CompteurBudget(appels_max=5, jetons_max=100)
        self.assertFalse(budget.consommer(1, 500))
        self.assertEqual(budget.jetons_consommes, 0)
        self.assertEqual(budget.appels_consommes, 0)

    def test_epuise(self):
        budget = CompteurBudget(appels_max=1)
        self.assertFalse(budget.epuise())
        budget.consommer(1)
        self.assertTrue(budget.epuise())

    def test_illimite(self):
        budget = CompteurBudget()
        self.assertIsNone(budget.appels_restants())
        self.assertIsNone(budget.jetons_restants())
        self.assertTrue(budget.consommer(10_000, 10_000_000))
        self.assertFalse(budget.epuise())

    def test_concurrence(self):
        """8 threads × 100 appels sur un budget de 800 : aucun dépassement."""
        budget = CompteurBudget(appels_max=800)
        def travailler():
            for _ in range(100):
                budget.consommer(1)
        threads = [threading.Thread(target=travailler) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(budget.appels_consommes, 800)
        self.assertEqual(budget.appels_restants(), 0)

    def test_etat_complet(self):
        budget = CompteurBudget(appels_max=3, jetons_max=30)
        budget.consommer(1, 10)
        self.assertEqual(budget.restants(),
                         {"appels_restants": 2, "jetons_restants": 20,
                          "appels_consommes": 1, "jetons_consommes": 10})


class TestArretPropreAuSeuil(unittest.TestCase):
    """R3 : budget dépassé → arrêt propre, état conservé, campagne interrompue."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_r3_campagne_interrompue(self):
        entrepot = EntrepotDouble()
        result = executer_campagne(config(budget_appels=1, entrepot=entrepot))
        self.assertEqual(result.statut, StatutCampagne.INTERROMPUE)
        self.assertEqual(result.appels, 1)

    def test_r3_etat_conserve(self):
        entrepot = EntrepotDouble()
        executer_campagne(config(budget_appels=1, entrepot=entrepot))
        executions = entrepot.lister("executions")
        self.assertEqual(len(executions), 3)
        self.assertEqual(len([e for e in executions if e["statut"] == "execute"]), 1)
        refuses = [e for e in executions if e["erreur"] == "budget_epuise"]
        self.assertEqual(len(refuses), 2)

    def test_r3_aucune_sonde_apres_le_seuil(self):
        cible = CibleDouble()
        executer_campagne(config(budget_appels=1, cible=cible))
        self.assertEqual(len(cible.appels), 1)

    def test_budget_jetons(self):
        result = executer_campagne(config(budget_jetons=10))
        self.assertEqual(result.statut, StatutCampagne.INTERROMPUE)

    def test_budget_suffisant(self):
        result = executer_campagne(config())
        self.assertEqual(result.statut, StatutCampagne.TERMINEE)
        self.assertEqual(result.appels, 3)

    def test_refus_journalise(self):
        journal = JournalDouble()
        executer_campagne(config(budget_appels=1, journal=journal))
        codes = [l["details"].get("code") for l in journal.refus()]
        self.assertIn("budget_epuise", codes)


if __name__ == "__main__":
    unittest.main()
