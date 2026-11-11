"""Tests des correctifs : proposition, autorisation, application (R10)."""

from __future__ import annotations

import unittest

from doubles_correctifs import (CibleFictive, INSTANT, JugeFictif, REPONSE_BLOQUEE,
                                REPONSE_FUITE, application_demo, correctif,
                                faux_refus, finding, mandat_valide, technique_a1)
from piege.correctifs.application import appliquer, annuler, est_applique, theme_du_correctif
from piege.correctifs.autorisation import autoriser, est_autorise, refuser
from piege.correctifs.boucle import BilanCorrection, boucle_complete, choisir_correctif
from piege.correctifs.controles import (controler_effet_de_bord,
                                        controler_regression,
                                        fermeture_complete,
                                        phrase_effet_de_bord)
from piege.correctifs.proposition import proposer, type_correctif
from piege.correctifs.rejeu import chemin_preuve, est_ferme, fermer, rejouer
from piege.erreurs import AutorisationHumaineAbsente, ErreurPiege
from piege.types import (Campagne, Correctif, Execution, FauxRefus, Finding,
                         SeveriteRefus, StatutCampagne, StatutCorrectif,
                         StatutFinding, StatutMandat, TypeCampagne,
                         TypeCorrectif, VerdictValeur, fixer_horloge)



class TestProposition(unittest.TestCase):
    """EF-40 et EF-41 : au moins un correctif, classé par effort et réduction."""

    def test_au_moins_un_correctif(self):
        self.assertTrue(proposer(finding(), catalogue={"A1": technique_a1()}))

    def test_types_deduits(self):
        propositions = proposer(finding(), catalogue={"A1": technique_a1()})
        types = {p.type for p in propositions}
        self.assertIn(TypeCorrectif.DOCUMENT, types)
        self.assertIn(TypeCorrectif.GARDE_FOU, types)
        self.assertIn(TypeCorrectif.PROMPT, types)

    def test_tri_par_priorite(self):
        """Réduction totale d'abord, puis effort minimal (annexe D)."""
        propositions = proposer(finding(), catalogue={"A1": technique_a1()})
        self.assertEqual(propositions[0].reduction_risque, "totale")
        self.assertEqual(propositions[0].type, TypeCorrectif.DOCUMENT)
        self.assertEqual(propositions[-1].reduction_risque, "partielle")

    def test_statut_propose(self):
        for proposition in proposer(finding(), catalogue={"A1": technique_a1()}):
            self.assertEqual(proposition.statut, StatutCorrectif.PROPOSE)
            self.assertTrue(proposition.contenu.strip())
            self.assertIn(proposition.effort, (1, 2, 3))

    def test_identifiants_uniques(self):
        propositions = proposer(finding(), catalogue={"A1": technique_a1()})
        identifiants = [p.id for p in propositions]
        self.assertEqual(len(identifiants), len(set(identifiants)))

    def test_sans_catalogue(self):
        """Sans catalogue, les suggestions par défaut de la famille s'appliquent."""
        propositions = proposer(finding())
        self.assertTrue(propositions)
        self.assertTrue(all(p.contenu for p in propositions))

    def test_type_correctif(self):
        self.assertIs(type_correctif("retrait_documentaire"), TypeCorrectif.DOCUMENT)
        self.assertIs(type_correctif("garde_fou_remuneration"),
                      TypeCorrectif.GARDE_FOU)
        self.assertIs(type_correctif("separation_donnees_instructions"),
                      TypeCorrectif.PROMPT)
        self.assertIs(type_correctif("politique_d_appel"), TypeCorrectif.POLITIQUE)

    def test_choix_du_correctif_applicable(self):
        propositions = proposer(finding(), catalogue={"A1": technique_a1()})
        choisi = choisir_correctif(propositions)
        self.assertIn(choisi.type, (TypeCorrectif.GARDE_FOU, TypeCorrectif.POLITIQUE))

    def test_choix_sans_proposition(self):
        self.assertIsNone(choisir_correctif([]))


class TestAutorisation(unittest.TestCase):
    """R10 : sans accord humain explicite, rien n'est appliqué."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_r10_sans_accord(self):
        with self.assertRaises(AutorisationHumaineAbsente):
            appliquer(correctif(), CibleFictive())

    def test_autorisation_nominee(self):
        corrige = autoriser(correctif(), "anne.rssi", "commanditaire")
        self.assertEqual(corrige.statut, StatutCorrectif.AUTORISE)
        self.assertEqual(corrige.autorise_par, "anne.rssi")
        self.assertEqual(corrige.autorise_le, INSTANT)
        self.assertTrue(est_autorise(corrige))

    def test_role_non_habilite(self):
        with self.assertRaises(AutorisationHumaineAbsente):
            autoriser(correctif(), "marc", "proprietaire")

    def test_analyste_habilite(self):
        self.assertTrue(est_autorise(autoriser(correctif(), "marc", "analyste")))

    def test_auteur_anonyme(self):
        with self.assertRaises(AutorisationHumaineAbsente):
            autoriser(correctif(), "", "commanditaire")

    def test_refus_humain(self):
        corrige = refuser(correctif(), "anne.rssi", "risque métier")
        self.assertEqual(corrige.statut, StatutCorrectif.REFUSE)
        self.assertIn("risque métier", corrige.effet_de_bord)

    def test_correctif_non_applicable(self):
        """Un correctif d'invite n'est jamais appliqué par le service."""
        invite = correctif(type=TypeCorrectif.PROMPT)
        with self.assertRaises(AutorisationHumaineAbsente) as ctx:
            autoriser(invite, "anne.rssi", "commanditaire")
        self.assertEqual(ctx.exception.details["regle"], "correctif.type")
        # Double garde : même marqué autorisé, l'application reste refusée.
        invite.statut = StatutCorrectif.AUTORISE
        invite.autorise_par = "anne.rssi"
        invite.autorise_le = INSTANT
        with self.assertRaises(ErreurPiege) as erreur:
            appliquer(invite, CibleFictive())
        self.assertEqual(erreur.exception.code, "correctif_non_applicable")


class TestApplication(unittest.TestCase):
    """Application limitée aux garde-fous et politiques."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self.cible = CibleFictive()

    def tearDown(self):
        fixer_horloge(None)

    def test_garde_fou_applique(self):
        corrige = autoriser(correctif(), "anne.rssi", "commanditaire")
        appliquer(corrige, self.cible)
        self.assertTrue(est_applique(corrige))
        self.assertEqual(corrige.statut, StatutCorrectif.APPLIQUE)
        self.assertIn("remuneration", self.cible.garde_fous)

    def test_theme_deduit(self):
        corrige = correctif(contenu="Garde-fou : bloquer les secrets et jetons.")
        from piege.correctifs.application import theme_du_correctif

        self.assertEqual(theme_du_correctif(corrige), "secrets")

    def test_annulation(self):
        corrige = autoriser(correctif(), "anne.rssi", "commanditaire")
        appliquer(corrige, self.cible)
        annuler(corrige, self.cible)
        self.assertEqual(self.cible.garde_fous, [])
        self.assertEqual(corrige.statut, StatutCorrectif.REFUSE)

    def test_cible_sans_support(self):
        class CibleMuette:
            pass

        corrige = autoriser(correctif(), "anne.rssi", "commanditaire")
        with self.assertRaises(NotImplementedError):
            appliquer(corrige, CibleMuette())


if __name__ == "__main__":
    unittest.main()
