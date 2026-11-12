"""Tests des évolutions Evo-01 : score de risque agrégé et vector CVSS-IA."""

from __future__ import annotations

import unittest

from piege.severite_risque import (GRADES, POIDS_SEVERITE, cvss_ia,
                                   cvss_score_base, dette_securite,
                                   score_risque_application)
from piege.types import (Famille, Finding, Severite, StatutFinding)


def finding(severite=Severite.CRITIQUE, statut=StatutFinding.OUVERT, impact=4,
            exploitabilite=4, exposition=2, famille=Famille.A,
            ouvert_le="2026-11-01T00:00:00Z", identifiant="F-1"):
    """Découverte de test."""
    return Finding(id=identifiant, application_id="APP", tenant_id="TEN",
                   campagne_id="CMP", technique_ids=["A1"], famille=famille,
                   severite=severite, impact=impact, exploitabilite=exploitabilite,
                   exposition=exposition, score=None, statut=statut, titre="t",
                   description="d", citation="c", preuve_ids=[], correctif_ids=[],
                   ouvert_le=ouvert_le)


class TestScoreRisque(unittest.TestCase):
    """#36 : score agrégé par application, reproductible."""

    def test_vide(self):
        resultat = score_risque_application([])
        self.assertEqual(resultat["score"], 0)
        self.assertEqual(resultat["grade"], "A")

    def test_une_critique(self):
        resultat = score_risque_application([finding()])
        self.assertEqual(resultat["brut"], 40)
        self.assertEqual(resultat["critiques_ouverts"], 1)
        self.assertIn(resultat["grade"], ("C", "D"))

    def test_pondération_par_sévérité(self):
        self.assertEqual(POIDS_SEVERITE[Severite.CRITIQUE], 40)
        self.assertGreater(POIDS_SEVERITE[Severite.CRITIQUE],
                           POIDS_SEVERITE[Severite.ELEVE])

    def test_fermee_non_comptee(self):
        resultat = score_risque_application([finding(statut=StatutFinding.FERME)])
        self.assertEqual(resultat["brut"], 0)
        self.assertEqual(resultat["ouverts"], 0)
        self.assertEqual(resultat["score"], 0)

    def test_plafond_a_100(self):
        findings = [finding(identifiant="F-%d" % i) for i in range(5)]
        self.assertEqual(score_risque_application(findings)["score"], 100)

    def test_grade_monotone(self):
        seuils = [s for s, _ in GRADES]
        self.assertEqual(seuils, sorted(seuils))

    def test_dette_majore(self):
        recente = score_risque_application(
            [finding(ouvert_le="2026-11-24T00:00:00Z")],
            maintenant="2026-11-25T00:00:00Z")
        ancienne = score_risque_application(
            [finding(ouvert_le="2026-01-01T00:00:00Z")],
            maintenant="2026-11-25T00:00:00Z")
        self.assertGreater(ancienne["majoration_dette"], recente["majoration_dette"])
        self.assertLessEqual(ancienne["majoration_dette"], 10.0)

    def test_reproductible(self):
        a = score_risque_application([finding()])
        b = score_risque_application([finding()])
        self.assertEqual(a, b)


class TestDette(unittest.TestCase):
    """La dette croît avec le temps sans correctif."""

    def test_ouverte(self):
        dette = dette_securite([finding(ouvert_le="2026-11-01T00:00:00Z")],
                               maintenant="2026-11-11T00:00:00Z")
        self.assertEqual(dette["ouverts"], 1)
        self.assertEqual(dette["jours_cumules"], 10.0)

    def test_fermee_exclue(self):
        dette = dette_securite([finding(statut=StatutFinding.FERME)],
                               maintenant="2026-11-11T00:00:00Z")
        self.assertEqual(dette["ouverts"], 0)
        self.assertEqual(dette["jours_cumules"], 0.0)


class TestCvssIa(unittest.TestCase):
    """#38 : vector CVSS v3.1 publiable, calculé par code."""

    def test_score_base_connue_7_5(self):
        vecteur = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U",
                   "C": "H", "I": "N", "A": "N"}
        self.assertEqual(cvss_score_base(vecteur), 7.5)

    def test_score_base_connue_9_8(self):
        vecteur = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U",
                   "C": "H", "I": "H", "A": "H"}
        self.assertEqual(cvss_score_base(vecteur), 9.8)

    def test_score_base_zero_si_pas_d_impact(self):
        vecteur = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U",
                   "C": "N", "I": "N", "A": "N"}
        self.assertEqual(cvss_score_base(vecteur), 0.0)

    def test_vecteur_trouve_critique(self):
        resultat = cvss_ia(finding(impact=4, exploitabilite=4, exposition=3))
        self.assertTrue(resultat["vecteur"].startswith("CVSS:3.1/"))
        self.assertEqual(resultat["metriques"]["C"], "H")
        self.assertEqual(resultat["metriques"]["AV"], "N")
        self.assertEqual(resultat["metriques"]["A"], "N")
        self.assertGreaterEqual(resultat["score_base"], 7.0)

    def test_disponibilite_toujours_nulle(self):
        """ENF-03 : Piège ne teste jamais la disponibilité."""
        for expo in (1, 2, 3):
            for famille in Famille:
                resultat = cvss_ia(finding(exposition=expo, famille=famille))
                self.assertEqual(resultat["metriques"]["A"], "N")

    def test_empoisonnement_integrite_et_portee(self):
        resultat = cvss_ia(finding(famille=Famille.F, impact=3))
        self.assertEqual(resultat["metriques"]["I"], "H")
        self.assertEqual(resultat["metriques"]["S"], "C")
        self.assertEqual(resultat["metriques"]["UI"], "R")

    def test_extension(self):
        self.assertEqual(cvss_ia(finding())["extension"], "PIEGE-1.0")

    def test_deterministe(self):
        self.assertEqual(cvss_ia(finding())["vecteur"],
                         cvss_ia(finding())["vecteur"])

    def test_score_borne(self):
        for severite_ in Severite:
            for expo in (1, 2, 3):
                score = cvss_ia(finding(severite=severite_, impact=None
                                        if severite_ is Severite.INDETERMINEE else 3,
                                        exposition=expo))["score_base"]
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 10.0)


if __name__ == "__main__":
    unittest.main()
