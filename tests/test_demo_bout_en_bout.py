"""Tests de bout en bout : la démonstration fonctionne sur la vraie cible.

Ces tests valident le jalon J+7 de la spécification (§27) : une campagne
complète s'exécute sur la cible de démonstration, avec la vraie cible
(`CibleLocaleDemo`), le vrai catalogue des 60 techniques et le vrai moteur.
Ils s'assurent que les moments clés de la vidéo (§25.2) sont reproductibles
hors ligne : la fuite A1, l'empoisonnement F3 et la politique de périmètre.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from piege.moteur import ConfigurationCampagne, executer_campagne
from piege.types import Environnement, Severite, fixer_horloge

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGUE = os.path.join(RACINE, "catalogue")
SPEC_CIBLE = os.path.join(RACINE, "demo", "cible", "guichet-rh.json")
INSTANT = "2026-11-24T09:14:03Z"


def charger():
    """Charge la cible, le catalogue, l'application et le mandat réels."""
    from piege.catalogue import charger_catalogue
    from piege.cibles import creer_cible
    from piege.securite import mandats
    from piege.types import Application, TypeApplication

    with open(SPEC_CIBLE, encoding="utf-8") as f:
        spec = json.load(f)
    spec["corpus"] = os.path.join(RACINE, "demo", "corpus")
    cible = creer_cible(spec)
    catalogue = charger_catalogue(CATALOGUE)
    application = Application(id="APP-guichet-rh", tenant_id="TEN-demo",
                              nom="Guichet RH", type=TypeApplication.RAG,
                              acces="local", modele="simule-local",
                              environnement=Environnement.TEST, exposition=2,
                              depot_document_autorise=True)
    mandat = mandats.signer(mandats.creer(
        tenant_id="TEN-demo", application_id="APP-guichet-rh",
        perimetre_techniques=["A1", "C1", "F3"],
        environnements=[Environnement.TEST],
        fenetre_debut="2026-11-01T00:00:00Z", fenetre_fin="2026-12-01T00:00:00Z",
        budget_appels=40, budget_jetons=500_000, production_autorisee=False,
        contact_urgence="demo"))
    return cible, catalogue, application, mandat


def configurer(graine=20261124, technique_ids=("A1", "C1", "F3"), **kw):
    """Configuration de campagne sur la cible et le catalogue réels."""
    from piege.stockage import creer_entrepot

    cible, catalogue, application, mandat = charger()
    entrepot = creer_entrepot({"type": "local",
                               "dossier": tempfile.mkdtemp(prefix="piege-e2e-")})
    valeurs = dict(mandat=mandat, application=application, cible=cible,
                   catalogue={t: catalogue[t] for t in technique_ids},
                   technique_ids=list(technique_ids), graine=graine,
                   parallelisme=1, entrepot=entrepot)
    valeurs.update(kw)
    return ConfigurationCampagne(**valeurs), entrepot


class TestDemonstration(unittest.TestCase):
    """Les moments clés de la démonstration, reproductibles hors ligne."""

    @classmethod
    def setUpClass(cls):
        if not (os.path.isfile(SPEC_CIBLE) and os.path.isdir(CATALOGUE)):
            raise unittest.SkipTest("catalogue ou cible de démonstration absents")

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def executions_de(self, technique_id):
        config, entrepot = configurer(technique_ids=[technique_id])
        executer_campagne(config)
        return entrepot.lister("executions")

    def test_a1_divulgue_la_grille(self):
        """Moment 0:45 : A1 obtient la grille des salaires, verdict réussi."""
        executions = self.executions_de("A1")
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0]["technique_id"], "A1")
        self.assertEqual(executions[0]["verdict"], "reussi")
        self.assertIn("32 400", executions[0]["reponse_brute"])

    def test_c1_extrait_l_invite(self):
        """C1 restitue l'invite système."""
        executions = self.executions_de("C1")
        self.assertIn("assistant RH du Guichet", executions[0]["reponse_brute"])

    def test_f3_relaie_le_document_depose(self):
        """Moment 1:05 : le document contradictoire est relayé, puis retiré."""
        from piege.familles.empoisonnement import executer
        from piege.securite.journal import Journal

        cible, catalogue, application, mandat = charger()
        technique = catalogue["F3"]
        mesures = executer(technique, cible, mandat, "idx-test-CMP-DEMO", 7,
                           Journal(), campagne_id="CMP-DEMO",
                           dossier_catalogue=CATALOGUE)
        par_nom = {m.nom: m for m in mesures}
        self.assertTrue(par_nom["relais"].valeur)
        self.assertTrue(par_nom["persistance"].detail["nettoye_apres_destruction"])


class TestPolitiqueEtReproductibilite(unittest.TestCase):
    """R4 (périmètre) et R13 (reproductibilité) sur la cible réelle."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(SPEC_CIBLE):
            raise unittest.SkipTest("cible de démonstration absente")

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_r4_hors_perimetre_sans_sonde(self):
        """Une technique hors macro-périmètre est refusée, aucune sonde envoyée."""
        cible, catalogue, application, mandat = charger()
        # D7 est hors périmètre : le mandat ne couvre que A1, C1, F3.
        config, entrepot = configurer(technique_ids=["D7"])
        config.catalogue = {"D7": catalogue["D7"]}
        config.mandat = mandat
        campagne = executer_campagne(config)
        self.assertEqual(campagne.techniques_executes, [])
        self.assertEqual(campagne.appels, 0)
        executions = entrepot.lister("executions")
        self.assertEqual(executions[0]["statut"], "refuse")
        self.assertEqual(executions[0]["erreur"], "hors_perimetre")

    def test_r13_reproductibilite(self):
        premiere = self.lancer(111)
        seconde = self.lancer(111)
        self.assertEqual(premiere.appels, seconde.appels)
        self.assertEqual(premiere.techniques_executes, seconde.techniques_executes)
        self.assertEqual(premiere.statut, seconde.statut)

    def test_r13_graines_distinctes(self):
        premiere = self.lancer(111)
        seconde = self.lancer(222)
        # Les sessions dérivent de la graine : elles diffèrent.
        self.assertNotEqual(premiere.graine, seconde.graine)

    def lancer(self, graine):
        config, _ = configurer(graine=graine, technique_ids=["A1"])
        return executer_campagne(config)


class TestSyntheseSurCibleReelle(unittest.TestCase):
    """La découverte A1 sort avec une sévérité critique, calculée par code."""

    @classmethod
    def setUpClass(cls):
        if not (os.path.isfile(SPEC_CIBLE) and os.path.isdir(CATALOGUE)):
            raise unittest.SkipTest("catalogue ou cible absents")

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_severite_critique(self):
        try:
            from piege.rapport.synthese import synthetiser_findings
        except ImportError:
            self.skipTest("lot 12 (rapport) non présent sur cette branche")
        from piege.types import Execution, depuis_dict

        cible, catalogue, application, mandat = charger()
        config, entrepot = configurer(technique_ids=["A1"])
        campagne = executer_campagne(config)
        executions = [depuis_dict(Execution, e) for e in
                      entrepot.lister("executions")]
        findings = synthetiser_findings(campagne, executions, application,
                                        catalogue)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severite, Severite.CRITIQUE)
        self.assertEqual(findings[0].score, 32)
        self.assertEqual(findings[0].exploitabilite, 4)


if __name__ == "__main__":
    unittest.main()