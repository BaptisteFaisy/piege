"""Tests des évolutions Evo-01 : garde-fous Bedrock, juge hétérogène, calibration."""

from __future__ import annotations

import unittest

from piege.agents.juge.calibration import (etalonner, matrice_confusion,
                                           seuil_optimal, verifier_cible)
from piege.agents.juge.heterogene import (confronter_multi, juger_heterogene,
                                          quorum_par_defaut)
from piege.correctifs.guardrails_bedrock import (THEMES_GARDE_FOU,
                                                 appliquer_garde_fou_bedrock,
                                                 construire_garde_fou,
                                                 resume_garde_fou,
                                                 verifier_garde_fou)
from piege.erreurs import FournisseurIndisponible
from piege.types import (Correctif, Famille, Finding, Severite, StatutCorrectif,
                         StatutFinding, Technique, TypeCorrectif, Verdict,
                         VerdictValeur, Environnement, ProductionAutorisee)


def correctif(type_=TypeCorrectif.GARDE_FOU, contenu="Garde-fou : bloquer la rémunération.",
              finding_id="FINDING-2026-0147"):
    """Correctif de garde-fou de test."""
    return Correctif(id="COR-1", finding_id=finding_id, application_id="APP",
                     tenant_id="TEN", type=type_, contenu=contenu, effort=1,
                     reduction_risque="forte", statut=StatutCorrectif.AUTORISE)


def finding(**kw) -> Finding:
    """Découverte critique de test."""
    valeurs = dict(id="FINDING-2026-0147", application_id="APP", tenant_id="TEN",
                   campagne_id="CMP", technique_ids=["A1"], famille=Famille.A,
                   severite=Severite.CRITIQUE, impact=4, exploitabilite=4,
                   exposition=2, score=32, statut=StatutFinding.OUVERT, titre="t",
                   description="d", citation="c", preuve_ids=[], correctif_ids=[],
                   ouvert_le="2026-11-01T00:00:00Z")
    valeurs.update(kw)
    return Finding(**valeurs)


def technique(identifiant="A1", tours=1, appels=2, famille=Famille.A, pre=None):
    """Technique de test."""
    return Technique(id=identifiant, famille=famille, nom="n", objectif="o",
                     preconditions=pre or [], environnement=[Environnement.TEST],
                     production=ProductionAutorisee.JAMAIS, budget_appels=appels,
                     tours_max=tours, sonde_initiale="s", mesures=[],
                     juge_reussi_si="r")


class TestGardeFousBedrock(unittest.TestCase):
    """#42 : traduction d'un correctif en garde-fou Bedrock, et application."""

    def test_construction_remuneration(self):
        spec = construire_garde_fou(correctif(), finding())
        self.assertEqual(spec["topicPolicy"]["topicsConfig"][0]["type"], "DENY")
        self.assertIn("Rémunération", spec["topicPolicy"]["topicsConfig"][0]["name"])
        self.assertTrue(spec["blockedInputMessaging"])

    def test_construction_politique_ancrage(self):
        spec = construire_garde_fou(correctif(type_=TypeCorrectif.POLITIQUE,
                                              contenu="Politique : pondérer par autorité."))
        self.assertTrue(spec["contextualGroundingPolicy"]["enabled"])
        self.assertEqual(spec["topicPolicy"]["topicsConfig"], [])

    def test_construction_donnees_personnelles_pii(self):
        spec = construire_garde_fou(correctif(
            contenu="Garde-fou : bloquer les données personnelles."))
        self.assertTrue(spec["sensitiveInformationPolicy"]["piiEntitiesConfig"])

    def test_nom_sans_caractere_interdit(self):
        spec = construire_garde_fou(correctif())
        self.assertRegex(spec["name"], r"^[A-Za-z0-9_-]+$")

    def test_resume(self):
        resume = resume_garde_fou(construire_garde_fou(correctif(), finding()))
        self.assertTrue(any("Rémunération" in s for s in resume["sujets_refuses"]))
        self.assertTrue(resume["entree_bloquee"])

    def test_themes_couverts(self):
        self.assertIn("remuneration", THEMES_GARDE_FOU)
        self.assertIn("injection", THEMES_GARDE_FOU)

    def test_application_creation(self):
        class Client:
            def __init__(self):
                self.crees = []

            def list_guardrails(self):
                return {"guardrails": []}

            def create_guardrail(self, **kw):
                self.crees.append(kw)
                return {"guardrailId": "gr-123"}

        client = Client()
        resume = appliquer_garde_fou_bedrock(correctif(), finding(), client=client)
        self.assertEqual(resume["action"], "cree")
        self.assertEqual(resume["identifiant"], "gr-123")
        self.assertEqual(len(client.crees), 1)

    def test_application_mise_a_jour(self):
        class Client:
            def __init__(self):
                self.maj = []

            def list_guardrails(self):
                return {"guardrails": [{"id": "gr-9", "name":
                                         construire_garde_fou(correctif())["name"]}]}

            def update_guardrail(self, **kw):
                self.maj.append(kw)

        client = Client()
        resume = appliquer_garde_fou_bedrock(correctif(), client=client)
        self.assertEqual(resume["action"], "mis_a_jour")
        self.assertEqual(resume["identifiant"], "gr-9")
        self.assertEqual(len(client.maj), 1)

    def test_verification(self):
        class Client:
            def list_guardrails(self):
                return {"guardrails": [{"id": "gr-1", "name": "x",
                                         "status": "READY", "version": "DRAFT"}]}

        self.assertEqual(verifier_garde_fou(Client(), "x")["statut"], "READY")
        self.assertEqual(verifier_garde_fou(Client(), "absent")["statut"], "absent")

    def test_sans_boto3(self):
        try:
            import boto3                                    # noqa: F401
        except ImportError:
            pass
        else:
            self.skipTest("boto3 installé")
        from piege.correctifs.guardrails_bedrock import client_bedrock

        with self.assertRaises(FournisseurIndisponible):
            client_bedrock()


class TestJugeHeterogene(unittest.TestCase):
    """#26 : plusieurs modèles différents, confrontation."""

    def verdict(self, valeur, impact=4, confiance=0.9, modele="m"):
        return Verdict(verdict=valeur, impact=impact, citation="x",
                       confiance=confiance, motif="m", garde_fou_declenche=False,
                       modele=modele)

    def test_quorum(self):
        self.assertEqual(quorum_par_defaut(2), 2)
        self.assertEqual(quorum_par_defaut(3), 2)
        self.assertEqual(quorum_par_defaut(4), 3)

    def test_unanime_reussi(self):
        fusion = confronter_multi([self.verdict(VerdictValeur.REUSSI, modele="a"),
                                   self.verdict(VerdictValeur.REUSSI, modele="b")])
        self.assertEqual(fusion.verdict, VerdictValeur.REUSSI)
        self.assertFalse(fusion.revue_humaine)
        self.assertIn("a", fusion.modele)

    def test_desaccord_revue(self):
        fusion = confronter_multi([self.verdict(VerdictValeur.REUSSI),
                                   self.verdict(VerdictValeur.ECHOUE, impact=1)])
        self.assertEqual(fusion.verdict, VerdictValeur.AMBIGU)
        self.assertTrue(fusion.revue_humaine)
        self.assertIsNone(fusion.impact)

    def test_majorite(self):
        """Majorité 2/3 : le verdict suit la majorité, mais le dissensus force la revue."""
        fusion = confronter_multi([self.verdict(VerdictValeur.REUSSI),
                                   self.verdict(VerdictValeur.REUSSI),
                                   self.verdict(VerdictValeur.ECHOUE, impact=1)])
        self.assertEqual(fusion.verdict, VerdictValeur.REUSSI)
        self.assertTrue(fusion.revue_humaine)

    def test_unanimite_sans_revue(self):
        fusion = confronter_multi([self.verdict(VerdictValeur.REUSSI, modele="a"),
                                   self.verdict(VerdictValeur.REUSSI, modele="b"),
                                   self.verdict(VerdictValeur.REUSSI, modele="c")])
        self.assertEqual(fusion.verdict, VerdictValeur.REUSSI)
        self.assertFalse(fusion.revue_humaine)

    def test_confiance_ponderee(self):
        fusion = confronter_multi([self.verdict(VerdictValeur.REUSSI, confiance=0.8),
                                   self.verdict(VerdictValeur.REUSSI, confiance=0.8)])
        self.assertLessEqual(fusion.confiance, 0.8)

    def test_juger_heterogene_avec_doubles(self):
        class Fournisseur:
            def __init__(self, nom, verdict):
                self.nom = nom
                self._v = verdict

            def sortie_structuree(self, messages, schema, graine):
                return {"verdict": self._v, "impact": 4 if self._v == "reussi" else 1,
                        "citation": "x", "confiance": 0.9, "motif": "m",
                        "garde_fou_declenche": False}

        fournisseurs = [Fournisseur("a", "reussi"), Fournisseur("b", "reussi")]
        verdict = juger_heterogene(technique(), "transcription", fournisseurs, 7)
        self.assertEqual(verdict.verdict, VerdictValeur.REUSSI)

    def test_juger_heterogene_desaccord(self):
        class Fournisseur:
            def __init__(self, nom, verdict):
                self.nom = nom
                self._v = verdict

            def sortie_structuree(self, messages, schema, graine):
                return {"verdict": self._v, "impact": 4 if self._v == "reussi" else 1,
                        "citation": "x", "confiance": 0.9, "motif": "m",
                        "garde_fou_declenche": False}

        fournisseurs = [Fournisseur("a", "reussi"), Fournisseur("b", "echoue")]
        verdict = juger_heterogene(technique(), "t", fournisseurs, 7)
        self.assertTrue(verdict.revue_humaine)

    def test_jury_incomplet(self):
        class Fournisseur:
            nom = "seul"

            def sortie_structuree(self, messages, schema, graine):
                return {"verdict": "reussi", "impact": 4, "citation": "x",
                        "confiance": 0.9, "motif": "m", "garde_fou_declenche": False}

        verdict = juger_heterogene(technique(), "t", [Fournisseur()], 7)
        self.assertTrue(verdict.revue_humaine)
        self.assertIn("jury_incomplet", verdict.motif)

    def test_aucun_fournisseur(self):
        with self.assertRaises(ValueError):
            juger_heterogene(technique(), "t", [], 7)


class TestCalibration(unittest.TestCase):
    """#28 : précision mesurée sur un jeu étiqueté, seuil recommandé."""

    def jeu(self):
        """80 % d'accord : 8 bons, 2 faux (1 FN, 1 FP)."""
        exemples = []
        for _ in range(7):
            exemples.append({"verdict": "reussi", "confiance": 0.95, "etiquette": "reussi"})
        exemples.append({"verdict": "echoue", "confiance": 0.9, "etiquette": "echoue"})
        exemples.append({"verdict": "echoue", "confiance": 0.4, "etiquette": "reussi"})  # FN
        exemples.append({"verdict": "reussi", "confiance": 0.3, "etiquette": "echoue"})  # FP
        return exemples

    def test_etalonner(self):
        resultat = etalonner(self.jeu())
        self.assertEqual(resultat["n"], 10)
        self.assertEqual(resultat["accord"], 0.8)
        self.assertEqual(resultat["faux_negatifs"], 1)
        self.assertEqual(resultat["faux_positifs"], 1)
        self.assertEqual(resultat["vrais_positifs"], 7)

    def test_matrice(self):
        matrice = matrice_confusion(self.jeu())
        self.assertEqual(matrice["reussi"]["reussi"], 7)
        self.assertEqual(matrice["echoue"]["reussi"], 1)

    def test_cible_non_atteinte(self):
        resultat = verifier_cible(self.jeu(), cible=0.90)
        self.assertFalse(resultat["conforme"])
        self.assertEqual(len(resultat["a_revoir"]), 2)

    def test_cible_atteinte(self):
        parfaits = [{"verdict": "reussi", "confiance": 0.9, "etiquette": "reussi"}] * 10
        self.assertTrue(verifier_cible(parfaits, 0.90)["conforme"])

    def test_seuil_optimal(self):
        resultat = seuil_optimal(self.jeu(), cible=0.90)
        self.assertIsNotNone(resultat["seuil_recommande"])
        self.assertTrue(resultat["candidats"])

    def test_seuil_filtre_les_faibles(self):
        """Un seuil haut écarte les verdicts peu sûrs (les 2 erreurs)."""
        resultat = seuil_optimal(self.jeu(), cible=1.0)
        choisi = resultat["choisi"]
        self.assertGreaterEqual(choisi["seuil"], 0.45)
        self.assertEqual(choisi["accord"], 1.0)

    def test_vide(self):
        self.assertEqual(etalonner([])["n"], 0)
        self.assertIsNone(seuil_optimal([])["seuil_recommande"])

    def test_enums_acceptes(self):
        exemples = [{"verdict": VerdictValeur.REUSSI, "confiance": 0.9,
                     "etiquette": VerdictValeur.REUSSI}]
        self.assertEqual(etalonner(exemples)["accord"], 1.0)


if __name__ == "__main__":
    unittest.main()
