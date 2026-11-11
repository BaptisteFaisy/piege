"""Tests d'arrêt d'urgence et de suspension/reprise (R5, ENF-14)."""

from __future__ import annotations

import time
import unittest

from piege.moteur import (ConfigurationCampagne, executer_campagne, reprendre,
                          suspendre)
from piege.moteur.arret import ArretUrgence, oublier
from piege.types import StatutCampagne, fixer_horloge

from doubles import application, mandat, technique
from doubles_moteur import (CibleDouble, EntrepotDouble, JournalDouble,
                            juge_double)

INSTANT = "2026-11-24T09:14:03Z"


def config(campagne_id="CMP-0042", **remplacements) -> ConfigurationCampagne:
    """Configuration hors ligne sur deux techniques."""
    valeurs = dict(mandat=mandat(perimetre_techniques=["A1", "F3"]),
                   application=application(), cible=CibleDouble(),
                   techniques=[technique(id="A1"), technique(id="F3")],
                   graine=20261124, parallelisme=1, juge=juge_double(),
                   journal=JournalDouble(), entrepot=EntrepotDouble(),
                   campagne_id=campagne_id)
    valeurs.update(remplacements)
    return ConfigurationCampagne(**valeurs)


class TestInterrupteur(unittest.TestCase):
    """L'interrupteur est atomique, daté et motivé."""

    def tearDown(self):
        fixer_horloge(None)
        oublier("CMP-test")

    def test_declenchement(self):
        fixer_horloge(INSTANT)
        arret = ArretUrgence()
        self.assertFalse(arret.actif)
        arret.declencher("test")
        self.assertTrue(arret.actif)
        self.assertEqual(arret.declenche_le, INSTANT)
        self.assertEqual(arret.motif, "test")

    def test_levee(self):
        arret = ArretUrgence(actif=True)
        arret.lever()
        self.assertFalse(arret.actif)
        self.assertEqual(arret.etat()["motif"], "")

    def test_registre_par_campagne(self):
        from piege.moteur.arret import arret_de

        suspendre("CMP-test")
        self.assertTrue(arret_de("CMP-test").actif)
        reprendre("CMP-test")
        self.assertFalse(arret_de("CMP-test").actif)

    def test_etat_serialisable(self):
        arret = ArretUrgence(actif=True, motif="incident")
        self.assertEqual(set(arret.etat()), {"actif", "motif", "declenche_le"})


class TestSuspension(unittest.TestCase):
    """R5 : suspension immédiate, état conservé, reprise possible."""

    def setUp(self):
        fixer_horloge(INSTANT)
        oublier("CMP-0042")

    def tearDown(self):
        fixer_horloge(None)
        oublier("CMP-0042")

    def test_arret_avant_lancement(self):
        result = executer_campagne(config(arrete_urgence=True))
        self.assertEqual(result.statut, StatutCampagne.SUSPENDUE)
        self.assertEqual(result.techniques_executes, [])

    def test_aucune_sonde_envoyee(self):
        cible = CibleDouble()
        executer_campagne(config(cible=cible, arrete_urgence=True))
        self.assertEqual(cible.appels, [])

    def test_refus_journalise(self):
        journal = JournalDouble()
        executer_campagne(config(journal=journal, arrete_urgence=True))
        codes = [l["details"].get("code") for l in journal.refus()]
        self.assertEqual(codes, ["arret_urgence", "arret_urgence"])

    def test_reprise_apres_suspension(self):
        suspendre("CMP-0042")
        self.assertEqual(executer_campagne(config()).statut,
                         StatutCampagne.SUSPENDUE)
        reprendre("CMP-0042")
        self.assertEqual(executer_campagne(config()).statut,
                         StatutCampagne.TERMINEE)

    def test_effet_immediat(self):
        """Un arrêt déclenché pendant la campagne bloque la technique suivante."""
        cible = CibleDouble()
        original = cible.sonder

        def sonder_puis_suspendre(demande, session, graine):
            reponse = original(demande, session, graine)
            suspendre("CMP-0042", "incident")
            return reponse

        cible.sonder = sonder_puis_suspendre
        debut = time.monotonic()
        result = executer_campagne(config(cible=cible))
        duree = time.monotonic() - debut
        self.assertEqual(result.statut, StatutCampagne.SUSPENDUE)
        self.assertLess(duree, 5.0)
        self.assertEqual(len(cible.appels), 1)


if __name__ == "__main__":
    unittest.main()
