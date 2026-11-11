"""Tests des grilles et agrégations de sévérité (lot 6)."""

from __future__ import annotations

import unittest

from piege import severite as s
from piege import severite_tableaux as t
from piege.types import (Famille, Finding, ProductionAutorisee, Severite,
                         SeveriteRefus, StatutFinding, Technique, FauxRefus,
                         ClasseRefus, CauseRefus)


def technique(identifiant, tours, appels, preconditions=None):
    """Technique de test pour la table d'exploitabilité."""
    return Technique(
        id=identifiant, famille=Famille.A, nom="n", objectif="o",
        preconditions=preconditions or [], environnement=[],
        production=ProductionAutorisee.JAMAIS, budget_appels=appels,
        tours_max=tours, sonde_initiale="?", mesures=[], juge_reussi_si="x")


def finding(identifiant, severite, tenant="TEN-acme"):
    """Découverte déjà classée, pour les agrégations."""
    return Finding(
        id=identifiant, application_id="APP-1", tenant_id=tenant,
        campagne_id="CMP-1", technique_ids=["A1"], famille=Famille.A,
        severite=severite, impact=4, exploitabilite=4, exposition=2, score=32,
        statut=StatutFinding.OUVERT, titre="t", description="d", citation="c",
        preuve_ids=[], correctif_ids=[], ouvert_le="2026-11-24T09:14:03Z")


def faux_refus(identifiant, frequence, criticite, minutes=12):
    """Faux refus classé, pour l'agrégation des pertes."""
    return FauxRefus(
        id=identifiant, campagne_id="CMP-1", application_id="APP-1",
        tenant_id="TEN-acme", demande_id="DL-1", reponse_ref="PRV-1",
        classe=ClasseRefus.REFUS, cause=CauseRefus.GARDE_FOU,
        frequence_mensuelle=frequence, criticite_metier=criticite,
        perte=s.perte(frequence, criticite),
        severite=s.severite_faux_refus(frequence, criticite),
        minutes_manuelles=minutes)


class TestGrilles(unittest.TestCase):
    """Grilles FR/EN alignées et complètes."""

    def test_decouvertes_fr_en_alignees(self):
        self.assertEqual(len(t.GRILLE_DECOUVERTES_FR["regles"]),
                         len(t.GRILLE_DECOUVERTES_EN["regles"]))
        self.assertEqual(set(t.GRILLE_DECOUVERTES_FR),
                         set(t.GRILLE_DECOUVERTES_EN))
        self.assertEqual(set(t.GRILLE_DECOUVERTES_FR["axes"]),
                         {"impact", "exploitabilite", "exposition"})

    def test_faux_refus_fr_en_alignees(self):
        self.assertEqual(len(t.GRILLE_FAUX_REFUS_FR["regles"]),
                         len(t.GRILLE_FAUX_REFUS_EN["regles"]))
        self.assertEqual(set(t.GRILLE_FAUX_REFUS_FR), set(t.GRILLE_FAUX_REFUS_EN))

    def test_acces_par_langue(self):
        self.assertIs(t.grille("fr"), t.GRILLE_DECOUVERTES_FR)
        self.assertIs(t.grille("en"), t.GRILLE_DECOUVERTES_EN)
        self.assertIs(t.grille("fr", faux_refus=True), t.GRILLE_FAUX_REFUS_FR)
        self.assertIs(t.grille("en", faux_refus=True), t.GRILLE_FAUX_REFUS_EN)
        self.assertIsNone(t.grille("de"))

    def test_formule_explicite(self):
        self.assertIn("impact", t.GRILLE_DECOUVERTES_FR["formule"])
        self.assertIn("perte", t.GRILLE_FAUX_REFUS_FR["formule"])
        self.assertIn("loss", t.GRILLE_FAUX_REFUS_EN["formule"])


class TestTableExploitabilite(unittest.TestCase):
    """La table reproduit le barème gelé, sans lecture de fichier."""

    def test_cohérence_avec_le_moteur(self):
        jeu = [technique("A1", 1, 2), technique("C1", 2, 3),
               technique("H1", 2, 4), technique("A4", 5, 8),
               technique("B7", 9, 7), technique("D6", 10, 10),
               technique("C5", 20, 20),
               technique("F3", 2, 6, ["depot_document_autorise"]),
               technique("G1", 1, 1), technique("E6", 1, 3),
               technique("D2", 3, 6), technique("H4", 12, 15)]
        table = t.exploitabilite_par_technique(jeu)
        self.assertEqual(len(table), 12)
        for element in jeu:
            self.assertEqual(table[element.id], s.exploitabilite(element))

    def test_cinq_cas_du_bareme(self):
        table = t.exploitabilite_par_technique([
            technique("A1", 1, 2), technique("C1", 2, 3), technique("H1", 2, 4),
            technique("A4", 5, 8), technique("D6", 10, 10),
            technique("F3", 2, 6, ["depot_document_autorise"])])
        self.assertEqual(table, {"A1": 4, "C1": 4, "H1": 3, "A4": 2, "D6": 1,
                                 "F3": 3})

    def test_vide(self):
        self.assertEqual(t.exploitabilite_par_technique([]), {})


class TestAggregats(unittest.TestCase):
    """Décomptes utilisés par le portail et le rapport."""

    def test_resume_toutes_les_classes(self):
        resume = t.resume_severites([])
        self.assertEqual(set(resume), {x.value for x in t.ORDRE_SEVERITES})
        self.assertEqual(sum(resume.values()), 0)

    def test_resume_compte(self):
        resume = t.resume_severites([
            finding("F-1", Severite.CRITIQUE), finding("F-2", Severite.CRITIQUE),
            finding("F-3", Severite.ELEVE), finding("F-4", Severite.INDETERMINEE)])
        self.assertEqual(resume["critique"], 2)
        self.assertEqual(resume["eleve"], 1)
        self.assertEqual(resume["indeterminee"], 1)
        self.assertEqual(resume["faible"], 0)

    def test_resume_faux_refus(self):
        resume = t.resume_faux_refus([faux_refus("R-1", 9, 4),
                                      faux_refus("R-2", 14, 3)])
        self.assertEqual(resume["par_severite"]["bloquant"], 1)
        self.assertEqual(resume["par_severite"]["majeur"], 1)
        self.assertEqual(resume["perte_totale"], 36 + 42)
        self.assertEqual(resume["heures_perdues"], round((9 + 14) * 12 / 60, 2))

    def test_resume_faux_refus_vide(self):
        resume = t.resume_faux_refus([])
        self.assertEqual(resume["perte_totale"], 0)
        self.assertEqual(resume["heures_perdues"], 0.0)


class TestAnnexeC(unittest.TestCase):
    """Les tableaux de référence sont conformes au moteur."""

    def test_lignes_decouvertes(self):
        for ligne in t.lignes_annexe_c():
            if ligne["impact"] is None:
                self.assertEqual(
                    s.severite(None, ligne["exploitabilite"], ligne["exposition"]),
                    ligne["severite"])
                continue
            self.assertEqual(
                s.score(ligne["impact"], ligne["exploitabilite"],
                        ligne["exposition"]), ligne["score"])
            self.assertEqual(
                s.severite(ligne["impact"], ligne["exploitabilite"],
                           ligne["exposition"]), ligne["severite"])

    def test_lignes_faux_refus(self):
        for ligne in t.lignes_annexe_c_refus():
            self.assertEqual(
                s.severite_faux_refus(ligne["frequence"], ligne["criticite"]),
                ligne["severite"])

    def test_sept_cas_de_decouvertes(self):
        self.assertEqual(len(t.lignes_annexe_c()), 7)
        self.assertEqual(len(t.lignes_annexe_c_refus()), 4)

    def test_classes_couvertes(self):
        classes = {ligne["severite"] for ligne in t.lignes_annexe_c()}
        self.assertIn(Severite.CRITIQUE, classes)
        self.assertIn(Severite.INDETERMINEE, classes)
        self.assertEqual(len({c.value for c in SeveriteRefus}),
                         len({l["severite"] for l in t.lignes_annexe_c_refus()}))


if __name__ == "__main__":
    unittest.main()
