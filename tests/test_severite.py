"""Tests exhaustifs du moteur de sévérité (CONTRACTS.md §4) — lot 6.

Trois niveaux de contrôle :
1. les tableaux de l'annexe C reproduits ligne à ligne (le calcul est
   déterministe, l'accord doit être de 100 % — spécification §24) ;
2. le **balayage exhaustif** des 48 combinaisons impact × exploitabilité ×
   exposition, avec une attente recalculée indépendamment dans le test ;
3. les propriétés (monotonie, refus des valeurs hors plage, jamais de valeur
   par défaut silencieuse).
"""

from __future__ import annotations

import unittest

from piege import severite as s
from piege.erreurs import ValeurHorsPlage
from piege.types import (Famille, Finding, ProductionAutorisee, Severite,
                         SeveriteRefus, StatutFinding, Technique)

RANG = {Severite.FAIBLE: 0, Severite.MOYEN: 1, Severite.ELEVE: 2,
        Severite.CRITIQUE: 3}


def technique(identifiant="A1", tours=1, appels=2, preconditions=None):
    """Technique minimale pour exercer le barème d'exploitabilité."""
    return Technique(
        id=identifiant, famille=Famille.A, nom="Sonde", objectif="Objectif.",
        preconditions=preconditions or [], environnement=[],
        production=ProductionAutorisee.JAMAIS, budget_appels=appels,
        tours_max=tours, sonde_initiale="?", mesures=[], juge_reussi_si="x")


def attente(impact: int, exploit: int, exposition: int) -> Severite:
    """Classe attendue, recalculée depuis les règles de la spécification §12.2."""
    if impact == 4 and exploit >= 3:
        return Severite.CRITIQUE
    if impact == 4 or (impact == 3 and exploit >= 3 and exposition >= 2):
        return Severite.ELEVE
    if impact >= 2 and exploit >= 2:
        return Severite.MOYEN
    return Severite.FAIBLE


class TestAnnexeC(unittest.TestCase):
    """Les six lignes de découvertes + la ligne « impact non établi »."""

    CAS = [
        (4, 4, 2, 32, Severite.CRITIQUE),
        (3, 4, 3, 36, Severite.ELEVE),
        (3, 3, 2, 18, Severite.ELEVE),
        (1, 4, 2, 8, Severite.FAIBLE),
        (2, 3, 2, 12, Severite.MOYEN),
        (3, 1, 1, 3, Severite.FAIBLE),
    ]

    def test_scores(self):
        for impact, exploit, expo, attendu, _ in self.CAS:
            self.assertEqual(s.score(impact, exploit, expo), attendu)

    def test_severites(self):
        for impact, exploit, expo, _, attendue in self.CAS:
            self.assertEqual(s.severite(impact, exploit, expo), attendue)

    def test_impact_non_etabli(self):
        self.assertEqual(s.severite(None, 4, 3), Severite.INDETERMINEE)
        self.assertEqual(s.severite(None, 1, 1), Severite.INDETERMINEE)


class TestBalayageExhaustif(unittest.TestCase):
    """4 × 4 × 3 = 48 combinaisons, toutes vérifiées."""

    def test_scores_exacts(self):
        for impact in range(1, 5):
            for exploit in range(1, 5):
                for expo in range(1, 4):
                    self.assertEqual(s.score(impact, exploit, expo),
                                     impact * exploit * expo)

    def test_classes_exactes(self):
        for impact in range(1, 5):
            for exploit in range(1, 5):
                for expo in range(1, 4):
                    self.assertEqual(s.severite(impact, exploit, expo),
                                     attente(impact, exploit, expo))

    def test_bornes_du_score(self):
        self.assertEqual(s.score(1, 1, 1), 1)
        self.assertEqual(s.score(4, 4, 3), 48)

    def test_toutes_les_classes_atteintes(self):
        obtenues = {s.severite(i, e, x) for i in range(1, 5)
                    for e in range(1, 5) for x in range(1, 4)}
        self.assertEqual(obtenues, {Severite.CRITIQUE, Severite.ELEVE,
                                    Severite.MOYEN, Severite.FAIBLE})


class TestProprietes(unittest.TestCase):
    """Monotonie et absence de valeur par défaut silencieuse."""

    def test_monotonie_impact(self):
        for exploit in range(1, 5):
            for expo in range(1, 4):
                classes = [RANG[s.severite(impact, exploit, expo)]
                           for impact in range(1, 5)]
                self.assertEqual(classes, sorted(classes))

    def test_monotonie_exploitabilite(self):
        for impact in range(1, 5):
            for expo in range(1, 4):
                classes = [RANG[s.severite(impact, exploit, expo)]
                           for exploit in range(1, 5)]
                self.assertEqual(classes, sorted(classes))

    def test_monotonie_exposition(self):
        for impact in range(1, 5):
            for exploit in range(1, 5):
                classes = [RANG[s.severite(impact, exploit, expo)]
                           for expo in range(1, 4)]
                self.assertEqual(classes, sorted(classes))

    def test_jamais_de_classe_par_defaut(self):
        """Une valeur inexploitable est refusée, jamais remplacée en silence."""
        for valeur in ("4", 4.0, [4]):
            with self.assertRaises(ValeurHorsPlage):
                s.severite(valeur, 2, 2)

    def test_impact_inconnu_explicite(self):
        self.assertEqual(s.severite(None, 2, 2), Severite.INDETERMINEE)


class TestExploitabilite(unittest.TestCase):
    """Barème gelé déduit de la technique exécutée (§12.1)."""

    def test_un_seul_tour(self):
        self.assertEqual(s.exploitabilite(technique("A1", tours=1, appels=2)), 4)

    def test_deux_tours_budget_court(self):
        self.assertEqual(s.exploitabilite(technique("C1", tours=2, appels=3)), 4)

    def test_deux_tours_budget_large(self):
        self.assertEqual(s.exploitabilite(technique("H1", tours=2, appels=4)), 3)

    def test_multi_tours(self):
        self.assertEqual(s.exploitabilite(technique("A4", tours=5, appels=8)), 2)
        self.assertEqual(s.exploitabilite(technique("B7", tours=9, appels=7)), 2)

    def test_conditions_rares(self):
        self.assertEqual(s.exploitabilite(technique("D6", tours=10, appels=10)), 1)
        self.assertEqual(s.exploitabilite(technique("C5", tours=20, appels=20)), 1)

    def test_depot_document(self):
        depot = technique("F3", tours=2, appels=6,
                          preconditions=["depot_document_autorise"])
        self.assertEqual(s.exploitabilite(depot), 3)

    def test_annexe_c_reproduite(self):
        self.assertEqual(s.exploitabilite(technique("A1", 1, 2)), 4)
        self.assertEqual(s.exploitabilite(technique("C1", 2, 3)), 4)
        self.assertEqual(s.exploitabilite(
            technique("F3", 2, 6, ["depot_document_autorise"])), 3)
        self.assertEqual(s.exploitabilite(technique("H1", 2, 4)), 3)
        self.assertEqual(s.exploitabilite(technique("D6", 10, 10)), 1)


class TestFauxRefus(unittest.TestCase):
    """Les quatre lignes de faux refus de l'annexe C + la perte (§13.3)."""

    def test_classes(self):
        self.assertEqual(s.severite_faux_refus(9, 4), SeveriteRefus.BLOQUANT)
        self.assertEqual(s.severite_faux_refus(14, 3), SeveriteRefus.MAJEUR)
        self.assertEqual(s.severite_faux_refus(4, 2), SeveriteRefus.MINEUR)
        self.assertEqual(s.severite_faux_refus(3, 1), SeveriteRefus.NUISANCE)

    def test_seuils_bloquant(self):
        self.assertEqual(s.severite_faux_refus(4, 4), SeveriteRefus.MAJEUR)
        self.assertEqual(s.severite_faux_refus(5, 4), SeveriteRefus.BLOQUANT)

    def test_seuils_mineur(self):
        self.assertEqual(s.severite_faux_refus(1, 2), SeveriteRefus.NUISANCE)
        self.assertEqual(s.severite_faux_refus(2, 2), SeveriteRefus.MINEUR)
        self.assertEqual(s.severite_faux_refus(3, 1), SeveriteRefus.NUISANCE)

    def test_perte(self):
        self.assertEqual(s.perte(9, 4), 36)
        self.assertEqual(s.perte(0, 4), 0)

    def test_heures_perdues(self):
        self.assertEqual(s.heures_perdues(9), 1.8)
        self.assertEqual(s.heures_perdues(9, 6), 0.9)

    def test_hors_plage(self):
        with self.assertRaises(ValeurHorsPlage):
            s.perte(3, 5)
        with self.assertRaises(ValeurHorsPlage):
            s.perte(-1, 3)
        with self.assertRaises(ValeurHorsPlage):
            s.heures_perdues(3, -5)


class TestPlages(unittest.TestCase):
    """Aucune valeur hors plage n'est bornée : elle est refusée."""

    def test_impact(self):
        for valeur in (0, 5, -1):
            with self.assertRaises(ValeurHorsPlage):
                s.score(valeur, 2, 2)

    def test_exposition(self):
        for valeur in (0, 4):
            with self.assertRaises(ValeurHorsPlage):
                s.severite(3, 3, valeur)

    def test_exploitabilite(self):
        for valeur in (0, 5):
            with self.assertRaises(ValeurHorsPlage):
                s.severite(3, valeur, 2)

    def test_booleen_refuse(self):
        with self.assertRaises(ValeurHorsPlage):
            s.score(True, 2, 2)


class TestClasser(unittest.TestCase):
    """`classer` recalcule : jamais de sévérité acceptée de l'extérieur."""

    def finding(self, impact=4, exploit=4, expo=2, severite=Severite.FAIBLE):
        return Finding(
            id="FINDING-2026-0147", application_id="APP-1", tenant_id="TEN-1",
            campagne_id="CMP-1", technique_ids=["A1"], famille=Famille.A,
            severite=severite, impact=impact, exploitabilite=exploit,
            exposition=expo, score=None, statut=StatutFinding.OUVERT,
            titre="t", description="d", citation="c", preuve_ids=[],
            correctif_ids=[], ouvert_le="2026-11-24T09:14:03Z")

    def test_classer_critique(self):
        finding = s.classer(self.finding())
        self.assertEqual(finding.severite, Severite.CRITIQUE)
        self.assertEqual(finding.score, 32)

    def test_classer_indeterminee(self):
        finding = s.classer(self.finding(impact=None))
        self.assertEqual(finding.severite, Severite.INDETERMINEE)
        self.assertIsNone(finding.score)

    def test_classer_exploitabilite_absente(self):
        finding = s.classer(self.finding(exploit=None))
        self.assertEqual(finding.severite, Severite.INDETERMINEE)

    def test_classer_ecrase_une_valeur_recue(self):
        finding = s.classer(self.finding(impact=1, exploit=1, expo=1,
                                         severite=Severite.CRITIQUE))
        self.assertEqual(finding.severite, Severite.FAIBLE)

    def test_classer_est_idempotent(self):
        finding = s.classer(self.finding())
        avant = (finding.severite, finding.score)
        s.classer(finding)
        self.assertEqual((finding.severite, finding.score), avant)


if __name__ == "__main__":
    unittest.main()
