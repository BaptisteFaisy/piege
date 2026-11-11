"""Tests de l'observabilité : compteurs, coûts mesurés, traces, budget, R17."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest

from piege.erreurs import FournisseurIndisponible, ValeurHorsPlage
from piege.observabilite import (Compteur, PROJECTION_ANNEXE_F, TARIFS, Trace,
                                 budget_restant, compte, cout, cout_mesure,
                                 cout_par_modele, cout_par_tenant,
                                 ecart_projection, exporter_jsonl,
                                 nouveau_compteur, reinitialiser, tarif, tracer,
                                 traces, vers_otlp)
from piege.types import (Campagne, Environnement, Mandat, StatutCampagne,
                         StatutMandat, TypeCampagne, fixer_horloge)

INSTANT = "2026-11-24T09:14:03Z"


def campagne(**kw) -> Campagne:
    """Campagne de test."""
    valeurs = dict(id="CMP-0042", mandat_id="MAN-2026-0001",
                   application_id="APP-guichet", tenant_id="TEN-acme",
                   type=TypeCampagne.COMPLETE, graine=7,
                   statut=StatutCampagne.EN_COURS, appels=12, jetons=50_000,
                   cout_mesure=1.25)
    valeurs.update(kw)
    return Campagne(**valeurs)


def mandat(**kw) -> Mandat:
    """Mandat de test avec budgets."""
    valeurs = dict(id="MAN-2026-0001", tenant_id="TEN-acme",
                   application_id="APP-guichet", perimetre_techniques=["A1"],
                   environnements=[Environnement.TEST],
                   fenetre_debut="2026-11-01T00:00:00Z",
                   fenetre_fin="2026-12-01T00:00:00Z", budget_appels=288,
                   budget_jetons=2_000_000, production_autorisee=False,
                   contact_urgence="x", signe_le=INSTANT, signature="",
                   statut=StatutMandat.VALIDE)
    valeurs.update(kw)
    return Mandat(**valeurs)


class TestCompteur(unittest.TestCase):
    """Compteurs cumulés, thread-safe, sérialisables."""

    def test_accumulation(self):
        compteur = Compteur()
        compteur.ajouter(appels=2, jetons_entree=1000, jetons_sortie=100,
                         cout=0.05, modele="nova-lite")
        compteur.ajouter(appels=1, jetons_entree=500, jetons_sortie=50,
                         cout=0.02, modele="nova-lite")
        self.assertEqual(compteur.appels, 3)
        self.assertEqual(compteur.jetons, 1650)
        self.assertEqual(compteur.cout, 0.07)

    def test_par_modele(self):
        compteur = Compteur()
        compteur.ajouter(appels=1, jetons_entree=100, cout=0.01, modele="a")
        compteur.ajouter(appels=2, jetons_entree=200, cout=0.02, modele="b")
        self.assertEqual(compteur.par_modele["a"]["appels"], 1)
        self.assertEqual(compteur.par_modele["b"]["appels"], 2)

    def test_concurrence(self):
        """8 threads × 500 ajouts : aucun compteur perdu."""
        compteur = Compteur()

        def travailler():
            for _ in range(500):
                compteur.ajouter(appels=1, jetons_entree=1, jetons_sortie=1)

        threads = [threading.Thread(target=travailler) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(compteur.appels, 4000)
        self.assertEqual(compteur.jetons, 8000)

    def test_fusion(self):
        premier = Compteur()
        premier.ajouter(appels=1, jetons_entree=10, cout=0.1, modele="a")
        second = Compteur()
        second.ajouter(appels=2, jetons_entree=20, cout=0.2, modele="b")
        premier.fusionner(second)
        self.assertEqual(premier.appels, 3)
        self.assertEqual(set(premier.par_modele), {"a", "b"})

    def test_serialisation(self):
        compteur = Compteur()
        compteur.ajouter(appels=1, jetons_entree=5, jetons_sortie=2)
        donnees = compteur.vers_dict()
        self.assertEqual(donnees["jetons"], 7)
        self.assertNotIn("_verrou", donnees)


class TestCouts(unittest.TestCase):
    """Les trois stratégies de l'annexe F sont retrouvées au centime près."""

    def test_table_unique(self):
        self.assertEqual(set(TARIFS), {"nova-lite", "modele-fort",
                                       "inferhub-flash"})
        self.assertEqual(TARIFS["nova-lite"], {"entree": 0.06, "sortie": 0.24})
        self.assertEqual(TARIFS["modele-fort"], {"entree": 3.00, "sortie": 15.00})

    def test_nova_lite(self):
        valeur = cout("nova-lite", 1_908_000, 212_400)
        self.assertAlmostEqual(valeur, 0.17, places=2)

    def test_modele_fort(self):
        valeur = cout("modele-fort", 1_908_000, 212_400)
        self.assertAlmostEqual(valeur, 8.91, places=2)

    def test_mixte(self):
        """Attaquant en Nova Lite + juge en modèle fort = 3,35 $ (annexe F.3)."""
        attaquant = cout("nova-lite", 1_260_000, 126_000)
        juge = cout("modele-fort", 648_000, 86_400)
        self.assertAlmostEqual(attaquant + juge, 3.35, places=2)

    def test_repli_inferhub(self):
        self.assertLess(cout("inferhub-flash", 1_000_000, 1_000_000), 0.01)

    def test_modele_inconnu_refuse(self):
        with self.assertRaises(ValeurHorsPlage):
            tarif("gpt-inexistant")
        with self.assertRaises(ValeurHorsPlage):
            cout("gpt-inexistant", 10, 10)

    def test_jetons_negatifs_refuses(self):
        with self.assertRaises(ValeurHorsPlage):
            cout("nova-lite", -1, 0)

    def test_cout_mesure_d_executions(self):
        executions = [{"jetons": 3850, "modele": "nova-lite", "verdict": None},
                      {"jetons": 3850, "modele": "nova-lite", "verdict": "reussi"}]
        valeur = cout_mesure(executions)
        attendu = cout("nova-lite", 3850, 0) * 2 + cout("modele-fort", 1500, 200)
        self.assertAlmostEqual(valeur, attendu, places=5)

    def test_cout_par_tenant(self):
        premier = Compteur()
        premier.ajouter(cout=1.5)
        second = Compteur()
        second.ajouter(cout=2.25)
        self.assertEqual(cout_par_tenant({"TEN-a": premier, "TEN-b": second}),
                         {"TEN-a": 1.5, "TEN-b": 2.25})

    def test_cout_par_modele(self):
        compteur = Compteur()
        compteur.ajouter(appels=1, cout=0.3, modele="modele-fort")
        self.assertEqual(cout_par_modele(compteur)["modele-fort"]["cout"], 0.3)


class TestTraces(unittest.TestCase):
    """Traces structurées, mesurées, exportables."""

    def setUp(self):
        fixer_horloge(INSTANT)
        reinitialiser()

    def tearDown(self):
        fixer_horloge(None)
        reinitialiser()

    def test_tracer(self):
        trace = tracer({"evenement": "sonde", "campagne_id": "CMP-1",
                        "technique_id": "A1", "tenant_id": "TEN-a"})
        self.assertEqual(trace["date"], INSTANT)
        self.assertEqual(trace["evenement"], "sonde")
        self.assertEqual(len(traces("CMP-1")), 1)

    def test_trace_contexte(self):
        with Trace("CMP-2", "attaque", technique_id="A1") as mesure:
            pass
        self.assertGreaterEqual(mesure.duree_ms, 0)
        self.assertEqual(traces("CMP-2")[0]["evenement"], "attaque")

    def test_trace_erreur(self):
        try:
            with Trace("CMP-3", "attaque"):
                raise ValueError("boom")
        except ValueError:
            pass
        self.assertIn("boom", traces("CMP-3")[0]["details"]["erreur"])

    def test_compteur_par_campagne(self):
        compteur = nouveau_compteur("CMP-4")
        compteur.ajouter(appels=1)
        self.assertIs(compte("CMP-4"), compteur)
        self.assertIsInstance(compte("CMP-inconnue"), Compteur)

    def test_export_jsonl(self):
        tracer({"evenement": "sonde", "campagne_id": "CMP-5"})
        tracer({"evenement": "verdict", "campagne_id": "CMP-5"})
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "sous", "traces.jsonl")
            self.assertEqual(exporter_jsonl("CMP-5", chemin), 2)
            with open(chemin, encoding="utf-8") as f:
                lignes = [json.loads(l) for l in f]
        self.assertEqual([l["evenement"] for l in lignes], ["sonde", "verdict"])

    def test_aucun_print_brut(self):
        import importlib

        module = importlib.import_module("piege.observabilite.traces")
        with open(module.__file__, encoding="utf-8") as f:
            self.assertNotIn("print(", f.read())


class TestBudget(unittest.TestCase):
    """Budget restant exposé au portail (EF-63)."""

    def test_reste_exact(self):
        etat = budget_restant(campagne(), mandat=mandat())
        self.assertEqual(etat["appels_restants"], 288 - 12)
        self.assertEqual(etat["jetons_restants"], 2_000_000 - 50_000)
        self.assertEqual(etat["cout_mesure"], 1.25)

    def test_parts(self):
        etat = budget_restant(campagne(appels=144), mandat=mandat())
        self.assertEqual(etat["part_appels"], 0.5)

    def test_avec_compteur(self):
        compteur = Compteur()
        compteur.ajouter(appels=30, jetons_entree=1000, jetons_sortie=500,
                         cout=2.5)
        etat = budget_restant(campagne(), compteur=compteur, mandat=mandat())
        self.assertEqual(etat["appels_consommes"], 30)
        self.assertEqual(etat["jetons_consommes"], 1500)
        self.assertEqual(etat["cout_mesure"], 2.5)

    def test_sans_mandat(self):
        etat = budget_restant(campagne())
        self.assertIsNone(etat["appels_restants"])
        self.assertIsNone(etat["part_appels"])


class TestEcarts(unittest.TestCase):
    """R17 : un écart supérieur à 25 % déclenche la revue."""

    def test_projection(self):
        self.assertEqual(PROJECTION_ANNEXE_F,
                         {"mixte": 3.35, "nova_lite": 0.17, "modele_fort": 8.91})

    def test_ecart_faible(self):
        resultat = ecart_projection(3.40, "mixte")
        self.assertFalse(resultat["depassement_25_pourcent"])
        self.assertLess(resultat["ecart_relatif"], 0.25)

    def test_ecart_fort(self):
        resultat = ecart_projection(6.00, "mixte")
        self.assertTrue(resultat["revue_requise"])
        self.assertGreater(resultat["ecart_relatif"], 0.25)

    def test_sous_estimation_signalee(self):
        resultat = ecart_projection(0.10, "mixte")
        self.assertTrue(resultat["depassement_25_pourcent"])

    def test_strategie_inconnue(self):
        with self.assertRaises(ValueError):
            ecart_projection(1.0, "inconnue")

    def test_chaque_strategie(self):
        for strategie, projection in PROJECTION_ANNEXE_F.items():
            self.assertFalse(ecart_projection(projection, strategie)
                             ["depassement_25_pourcent"])


class TestAgentCore(unittest.TestCase):
    """Projection OTLP et repli explicite hors AWS."""

    def setUp(self):
        reinitialiser()

    def tearDown(self):
        reinitialiser()

    def test_otlp(self):
        tracer({"evenement": "sonde", "campagne_id": "CMP-9",
                "technique_id": "A1", "tenant_id": "TEN-a"})
        charge = vers_otlp("CMP-9")
        spans = charge["resourceSpans"][0]["scopeSpans"][0]["spans"]
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["name"], "sonde")

    def test_metrics_incluses(self):
        compteur = nouveau_compteur("CMP-10")
        compteur.ajouter(appels=2, cout=0.5)
        self.assertEqual(vers_otlp("CMP-10", compteur)["metrics"]["appels"], 2)

    def test_sans_boto3(self):
        from piege.observabilite.agentcore import AdaptateurObservability

        try:
            import boto3                                    # noqa: F401
        except ImportError:
            pass
        else:
            self.skipTest("boto3 installé : le repli n'est pas exercé")
        with self.assertRaises(FournisseurIndisponible):
            AdaptateurObservability().client()

    def test_avec_client_double(self):
        from piege.observabilite.agentcore import AdaptateurObservability

        publies = []

        class Client:
            def put_log_events(self, **charge):
                publies.append(charge)

        tracer({"evenement": "sonde", "campagne_id": "CMP-11"})
        nombre = AdaptateurObservability(client=Client()).publier("CMP-11")
        self.assertEqual(nombre, 1)
        self.assertEqual(publies[0]["logStreamName"], "CMP-11")

    def test_publication_vide(self):
        from piege.observabilite.agentcore import AdaptateurObservability

        self.assertEqual(AdaptateurObservability(client=object()).publier("CMP-x"), 0)


if __name__ == "__main__":
    unittest.main()
