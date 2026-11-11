"""Tests de l'orchestrateur : campagne complète, parallélisme, journal."""

from __future__ import annotations

import unittest

from piege.moteur import ConfigurationCampagne, executer_campagne, preparer
from piege.moteur.orchestrateur import executer_technique
from piege.moteur.configuration import ConfigurationTechnique
from piege.types import (Campagne, StatutCampagne, TypeCampagne, VerdictValeur,
                         fixer_horloge)

from doubles import application, campagne, mandat, technique
from doubles_moteur import (CibleDouble, EntrepotDouble, JournalDouble,
                            REPONSE_FUITE, VerdictDouble, juge_double)

INSTANT = "2026-11-24T09:14:03Z"


def config(**remplacements) -> ConfigurationCampagne:
    """Configuration de campagne hors ligne, entièrement injectée."""
    valeurs = dict(mandat=mandat(), application=application(),
                   cible=CibleDouble(), techniques=[technique()],
                   graine=20261124, parallelisme=1, juge=juge_double(),
                   journal=JournalDouble(), entrepot=EntrepotDouble())
    valeurs.update(remplacements)
    return ConfigurationCampagne(**valeurs)


class TestCampagne(unittest.TestCase):
    """Une campagne s'exécute, se compte et se journalise."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_statut_termine(self):
        result = executer_campagne(config())
        self.assertEqual(result.statut, StatutCampagne.TERMINEE)
        self.assertEqual(result.debutee_le, INSTANT)
        self.assertEqual(result.terminee_le, INSTANT)

    def test_compteurs_agreges(self):
        result = executer_campagne(config())
        self.assertEqual(result.appels, 1)
        self.assertGreater(result.jetons, 0)

    def test_techniques_executes(self):
        result = executer_campagne(config())
        self.assertEqual(result.techniques_executes, ["A1"])
        self.assertEqual(result.techniques_prevues, ["A1"])

    def test_verdict_pose_par_le_juge(self):
        juge = juge_double(VerdictDouble(verdict=VerdictValeur.REUSSI, impact=4))
        entrepot = EntrepotDouble()
        executer_campagne(config(juge=juge, entrepot=entrepot))
        executions = entrepot.lister("executions")
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0]["verdict"], "reussi")
        self.assertEqual(executions[0]["impact"], 4)

    def test_campagne_persistee(self):
        entrepot = EntrepotDouble()
        result = executer_campagne(config(entrepot=entrepot))
        self.assertEqual(entrepot.lire("campagnes", result.id)["statut"],
                         "terminee")

    def test_sonde_envoyee_a_la_cible(self):
        cible = CibleDouble()
        executer_campagne(config(cible=cible))
        self.assertEqual(len(cible.appels), 1)
        self.assertIn("grille", cible.appels[0]["demande"])

    def test_session_isolee_par_technique(self):
        cible = CibleDouble()
        executer_campagne(config(cible=cible,
                                 techniques=[technique(), technique(id="F3")]))
        sessions = {a["session"] for a in cible.appels}
        self.assertEqual(len(sessions), 2)

    def test_journal_rempli(self):
        journal = JournalDouble()
        executer_campagne(config(journal=journal))
        quois = [l["quoi"] for l in journal.lignes]
        self.assertIn("campagne_terminee", quois)
        self.assertIn("verdict", quois)


class TestParallelisme(unittest.TestCase):
    """Le parallélisme est borné et ne change pas le résultat."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_resultats_identiques(self):
        techniques = [technique(id="A1"), technique(id="F3"),
                      technique(id="C1")]
        large = mandat(perimetre_techniques=["A1", "F3", "C1"])
        sequentiel = executer_campagne(config(mandat=large,
                                              techniques=techniques,
                                              parallelisme=1))
        parallele = executer_campagne(config(mandat=large, techniques=techniques,
                                             parallelisme=4))
        self.assertEqual(sequentiel.appels, parallele.appels)
        self.assertEqual(sorted(sequentiel.techniques_executes),
                         sorted(parallele.techniques_executes))

    def test_parallelisme_borne(self):
        from piege.erreurs import ValeurHorsPlage

        with self.assertRaises(ValeurHorsPlage):
            executer_campagne(config(parallelisme=99))
        with self.assertRaises(ValeurHorsPlage):
            executer_campagne(config(parallelisme=0))


class TestPreparation(unittest.TestCase):
    """La préparation résout tout avant la première sonde."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_contexte_complet(self):
        contexte = preparer(config())
        self.assertEqual(contexte.mandat.id, "MAN-2026-0001")
        self.assertEqual(len(contexte.techniques), 1)
        self.assertIsNotNone(contexte.budget)
        self.assertIsNotNone(contexte.evaluateur)

    def test_mandat_invalide_bloque(self):
        from piege.erreurs import MandatInvalide
        from piege.types import StatutMandat

        brouillon = mandat()
        brouillon.statut = StatutMandat.BROUILLON
        with self.assertRaises(MandatInvalide):
            preparer(config(mandat=brouillon))

    def test_mandat_expire_bloque(self):
        from piege.erreurs import MandatExpire

        expire = mandat(fenetre_fin="2026-11-20T00:00:00Z")
        with self.assertRaises(MandatExpire):
            preparer(config(mandat=expire))

    def test_budget_vient_du_mandat(self):
        contexte = preparer(config())
        self.assertEqual(contexte.budget.appels_max, 288)

    def test_budget_resserre_par_la_config(self):
        contexte = preparer(config(budget_appels=5))
        self.assertEqual(contexte.budget.appels_max, 5)

    def test_budget_ne_peut_pas_elargir(self):
        contexte = preparer(config(budget_appels=10_000))
        self.assertEqual(contexte.budget.appels_max, 288)


class TestRejeu(unittest.TestCase):
    """EF-54 : rejouer une technique précise depuis un finding."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_rejeu_identique(self):
        cible = CibleDouble()
        configuration = ConfigurationTechnique(
            technique=technique(), mandat=mandat(), cible=cible,
            campagne=campagne(), graine=20261124, juge=juge_double(),
            journal=JournalDouble(), entrepot=EntrepotDouble())
        premier = executer_technique(configuration)
        second = executer_technique(ConfigurationTechnique(
            technique=technique(), mandat=mandat(), cible=CibleDouble(),
            campagne=campagne(), graine=20261124, juge=juge_double(),
            journal=JournalDouble(), entrepot=EntrepotDouble()))
        self.assertEqual(premier.verdict, second.verdict)
        self.assertEqual(premier.sondes_envoyees, second.sondes_envoyees)
        self.assertEqual(premier.graine, second.graine)


class TestTypeCampagne(unittest.TestCase):
    """Le type de campagne est conservé (complète, ciblée, famille, rejeu)."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_types(self):
        for valeur in TypeCampagne:
            result = executer_campagne(config(type=valeur))
            self.assertEqual(result.type, valeur)

    def test_campagne_fournie_conservee(self):
        fournie = Campagne(id="CMP-9999", mandat_id="MAN-2026-0001",
                           application_id="APP-guichet", tenant_id="TEN-acme",
                           type=TypeCampagne.REJEU, graine=7,
                           statut=StatutCampagne.PLANIFIEE)
        result = executer_campagne(config(campagne=fournie))
        self.assertEqual(result.id, "CMP-9999")
        self.assertEqual(result.type, TypeCampagne.REJEU)

    def test_reponse_de_cible_utilisee(self):
        cible = CibleDouble(reponses=[REPONSE_FUITE])
        entrepot = EntrepotDouble()
        executer_campagne(config(cible=cible, entrepot=entrepot))
        execution = entrepot.lister("executions")[0]
        self.assertIn("32 400", execution["reponse_brute"])


if __name__ == "__main__":
    unittest.main()
