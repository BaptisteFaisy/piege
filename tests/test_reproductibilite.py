"""Tests de reproductibilité (R13, ENF-05, KPI-8) et des graines dérivées."""

from __future__ import annotations

import unittest

from piege.moteur import ConfigurationCampagne, executer_campagne
from piege.moteur.graine import (choisir, graine_etiquetee, graine_technique,
                                 graine_tour, melanger, session_id)
from piege.types import fixer_horloge

from doubles import application, mandat, technique
from doubles_moteur import (CibleDouble, EntrepotDouble, JournalDouble,
                            VerdictDouble, juge_double)

INSTANT = "2026-11-24T09:14:03Z"


def config(graine=20261124, **remplacements) -> ConfigurationCampagne:
    """Configuration déterministe sur deux techniques."""
    valeurs = dict(mandat=mandat(perimetre_techniques=["A1", "F3"]),
                   application=application(), cible=CibleDouble(),
                   techniques=[technique(id="A1"), technique(id="F3")],
                   graine=graine, parallelisme=1,
                   juge=juge_double(VerdictDouble()),
                   journal=JournalDouble(), entrepot=EntrepotDouble())
    valeurs.update(remplacements)
    return ConfigurationCampagne(**valeurs)


def empreintes(entrepot: EntrepotDouble) -> list:
    """Empreinte stable d'une campagne : verdicts, sondes, jetons par technique."""
    return sorted((e["technique_id"], e["verdict"], e["impact"],
                   tuple(e["sondes_envoyees"]), e["jetons"], e["graine"])
                  for e in entrepot.lister("executions"))


class TestGraines(unittest.TestCase):
    """Toutes les graines dérivent de la graine de campagne, sans `hash()`."""

    def test_determinisme(self):
        self.assertEqual(graine_technique(7, "A1"), graine_technique(7, "A1"))

    def test_sensible_a_la_technique(self):
        self.assertNotEqual(graine_technique(7, "A1"), graine_technique(7, "A2"))

    def test_sensible_a_la_campagne(self):
        self.assertNotEqual(graine_technique(7, "A1"), graine_technique(8, "A1"))

    def test_tours_distincts(self):
        graines = {graine_tour(7, "A1", tour) for tour in range(5)}
        self.assertEqual(len(graines), 5)

    def test_stable_entre_processus(self):
        """`hash_stable` ne dépend pas du sel du processus (blake2b)."""
        self.assertEqual(graine_etiquetee(1, "x"), graine_etiquetee(1, "x"))
        self.assertLess(graine_etiquetee(2 ** 40, "x"), 2 ** 32)

    def test_session_isolee(self):
        self.assertNotEqual(session_id(7, "A1"), session_id(7, "F3"))
        self.assertTrue(session_id(7, "A1").startswith("S-A1-"))

    def test_choix_deterministe(self):
        elements = ["a", "b", "c", "d"]
        self.assertEqual(choisir(elements, 7, "A1"), choisir(elements, 7, "A1"))

    def test_choix_sensible_a_l_etiquette(self):
        elements = list(range(50))
        self.assertNotEqual(choisir(elements, 7, "A1"),
                            choisir(elements, 7, "B2"))

    def test_choix_vide(self):
        with self.assertRaises(ValueError):
            choisir([], 1, "A1")

    def test_melange_deterministe(self):
        elements = list(range(20))
        self.assertEqual(melanger(elements, 3, "A1"), melanger(elements, 3, "A1"))
        self.assertEqual(sorted(melanger(elements, 3, "A1")), elements)


class TestReproductibilite(unittest.TestCase):
    """R13 : deux campagnes à graine identique donnent le même verdict."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_r13_verdicts_identiques(self):
        premier = EntrepotDouble()
        second = EntrepotDouble()
        executer_campagne(config(entrepot=premier))
        executer_campagne(config(entrepot=second))
        self.assertEqual(empreintes(premier), empreintes(second))

    def test_r13_sondes_identiques(self):
        premiere_cible = CibleDouble()
        seconde_cible = CibleDouble()
        executer_campagne(config(cible=premiere_cible))
        executer_campagne(config(cible=seconde_cible))
        self.assertEqual([a["demande"] for a in premiere_cible.appels],
                         [a["demande"] for a in seconde_cible.appels])
        self.assertEqual([a["session"] for a in premiere_cible.appels],
                         [a["session"] for a in seconde_cible.appels])

    def test_graines_differentes_sessions_differentes(self):
        premiere = CibleDouble()
        seconde = CibleDouble()
        executer_campagne(config(graine=1, cible=premiere))
        executer_campagne(config(graine=2, cible=seconde))
        self.assertNotEqual([a["session"] for a in premiere.appels],
                            [a["session"] for a in seconde.appels])

    def test_parallelisme_sans_effet(self):
        sequentiel = EntrepotDouble()
        parallele = EntrepotDouble()
        executer_campagne(config(parallelisme=1, entrepot=sequentiel))
        executer_campagne(config(parallelisme=4, entrepot=parallele))
        self.assertEqual(empreintes(sequentiel), empreintes(parallele))

    def test_dix_repetitions(self):
        reference = None
        for _ in range(10):
            entrepot = EntrepotDouble()
            executer_campagne(config(entrepot=entrepot))
            if reference is None:
                reference = empreintes(entrepot)
            self.assertEqual(empreintes(entrepot), reference)


if __name__ == "__main__":
    unittest.main()
