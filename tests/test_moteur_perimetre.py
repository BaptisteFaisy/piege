"""Tests du périmètre côté moteur : R1 (pas de mandat), R4 (hors périmètre)."""

from __future__ import annotations

import unittest

from piege.erreurs import ErreurPiege, MandatExpire, MandatInvalide
from piege.moteur import ConfigurationCampagne, executer_campagne
from piege.types import Environnement, StatutMandat, fixer_horloge

from doubles import application, mandat, technique
from doubles_moteur import (CibleDouble, EntrepotDouble, JournalDouble,
                            juge_double)

INSTANT = "2026-11-24T09:14:03Z"


def config(**remplacements) -> ConfigurationCampagne:
    """Configuration hors ligne ; le mandat couvre A1 et F3 seulement."""
    valeurs = dict(mandat=mandat(), application=application(),
                   cible=CibleDouble(), techniques=[technique()],
                   graine=20261124, parallelisme=1, juge=juge_double(),
                   journal=JournalDouble(), entrepot=EntrepotDouble())
    valeurs.update(remplacements)
    return ConfigurationCampagne(**valeurs)


class TestSansMandat(unittest.TestCase):
    """R1 : aucune exécution sans mandat valide, aucune sonde envoyée."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_mandat_absent(self):
        with self.assertRaises(ErreurPiege) as ctx:
            executer_campagne(config(mandat=None, mandat_id=""))
        self.assertEqual(ctx.exception.code, "mandat_invalide")

    def test_mandat_inconnu_de_l_entrepot(self):
        with self.assertRaises(ErreurPiege):
            executer_campagne(config(mandat=None, mandat_id="MAN-2026-9999"))

    def test_mandat_en_brouillon(self):
        brouillon = mandat(statut=StatutMandat.BROUILLON, signature="")
        with self.assertRaises(MandatInvalide):
            executer_campagne(config(mandat=brouillon))

    def test_r2_mandat_expire(self):
        expire = mandat(fenetre_fin="2026-11-20T00:00:00Z")
        with self.assertRaises(MandatExpire):
            executer_campagne(config(mandat=expire))

    def test_aucune_sonde_envoyee(self):
        cible = CibleDouble()
        with self.assertRaises(ErreurPiege):
            executer_campagne(config(mandat=None, cible=cible))
        self.assertEqual(cible.appels, [])


class TestHorsPerimetre(unittest.TestCase):
    """R4 : cible ou technique hors périmètre → refus tracé, pas de sonde."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_technique_hors_perimetre(self):
        entrepot = EntrepotDouble()
        result = executer_campagne(config(techniques=[technique(id="D1")],
                                          entrepot=entrepot))
        executions = entrepot.lister("executions")
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0]["statut"], "refuse")
        self.assertEqual(executions[0]["erreur"], "hors_perimetre")
        self.assertEqual(result.techniques_executes, [])

    def test_aucune_sonde_sur_refus(self):
        cible = CibleDouble()
        executer_campagne(config(techniques=[technique(id="D1")], cible=cible))
        self.assertEqual(cible.appels, [])

    def test_cible_hors_perimetre(self):
        autre = application(id="APP-autre")
        entrepot = EntrepotDouble()
        executer_campagne(config(application=autre, entrepot=entrepot))
        executions = entrepot.lister("executions")
        self.assertEqual(executions[0]["erreur"], "hors_perimetre")
        self.assertEqual(executions[0]["motif"].find("hors du périmètre") > 0,
                         True)

    def test_refus_journalise_avec_la_regle(self):
        journal = JournalDouble()
        executer_campagne(config(techniques=[technique(id="D1")],
                                 journal=journal))
        refus = journal.refus()
        self.assertEqual(len(refus), 1)
        self.assertEqual(refus[0]["details"]["regle"], "perimetre.technique")
        self.assertEqual(refus[0]["details"]["code"], "hors_perimetre")

    def test_environnement_non_couvert(self):
        production = application(environnement=Environnement.PROD)
        entrepot = EntrepotDouble()
        executer_campagne(config(application=production, entrepot=entrepot))
        executions = entrepot.lister("executions")
        self.assertEqual(executions[0]["erreur"], "hors_perimetre")

    def test_production_interdite_par_le_catalogue(self):
        """Une technique `jamais` en production est refusée même avec mandat."""
        from piege.types import ProductionAutorisee

        jamais = technique(id="A1", environnement=[Environnement.PROD],
                           production=ProductionAutorisee.JAMAIS)
        autorise = mandat(perimetre_techniques=["A1"],
                          environnements=[Environnement.PROD],
                          production_autorisee=True)
        cible = application(environnement=Environnement.PROD)
        entrepot = EntrepotDouble()
        executer_campagne(config(mandat=autorise, application=cible,
                                 techniques=[jamais], entrepot=entrepot))
        executions = entrepot.lister("executions")
        self.assertEqual(executions[0]["erreur"], "production_interdite")

    def test_melange_autorise_et_refuse(self):
        entrepot = EntrepotDouble()
        result = executer_campagne(
            config(techniques=[technique(id="A1"), technique(id="D1")],
                   entrepot=entrepot))
        self.assertEqual(result.techniques_executes, ["A1"])
        statuts = sorted(e["statut"] for e in entrepot.lister("executions"))
        self.assertEqual(statuts, ["execute", "refuse"])


class TestTechniquesInconnues(unittest.TestCase):
    """Une technique absente du catalogue est une erreur explicite."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_identifiant_inconnu(self):
        from piege.erreurs import TechniqueInconnue

        with self.assertRaises(TechniqueInconnue):
            executer_campagne(config(techniques=None, technique_ids=["ZZ9"],
                                     catalogue={"A1": technique()}))

    def test_catalogue_injecte(self):
        result = executer_campagne(config(techniques=None,
                                          technique_ids=["A1"],
                                          catalogue={"A1": technique()}))
        self.assertEqual(result.techniques_executes, ["A1"])

    def test_filtrage_par_famille(self):
        from piege.types import Famille

        catalogue = {"A1": technique(id="A1"), "F3": technique(id="F3",
                                                               famille=Famille.F)}
        result = executer_campagne(config(techniques=None,
                                          familles=[Famille.F],
                                          catalogue=catalogue,
                                          mandat=mandat(
                                              perimetre_techniques=["A1", "F3"])))
        self.assertEqual(result.techniques_executes, ["F3"])

    def test_catalogue_complet_sans_selection(self):
        catalogue = {"A1": technique(id="A1"), "F3": technique(id="F3")}
        result = executer_campagne(config(techniques=None,
                                          catalogue=catalogue))
        self.assertEqual(sorted(result.techniques_executes), ["A1", "F3"])


if __name__ == "__main__":
    unittest.main()
