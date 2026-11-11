"""Tests des correctifs : rejeu, contrôles et boucle complète (R11, R12)."""

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



class TestRejeu(unittest.TestCase):
    """R11 : application, rejeu, preuve de fermeture datée."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def rejeu(self, cible=None, **kw):
        valeurs = dict(finding=finding(), cible=cible or CibleFictive(),
                       mandat=mandat_valide(), graine=7,
                       technique=technique_a1(), juge=JugeFictif())
        valeurs.update(kw)
        return rejouer(**valeurs)

    def test_avant_correctif_encore_ouvert(self):
        execution, preuve = self.rejeu()
        self.assertFalse(est_ferme(execution))
        self.assertEqual(preuve.type, "rejeu")
        self.assertTrue(preuve.empreinte.startswith("sha256:"))

    def test_apres_correctif_bloque(self):
        cible = CibleFictive()
        cible.ajouter_garde_fou("remuneration")
        execution, preuve = self.rejeu(cible=cible)
        self.assertTrue(est_ferme(execution))
        self.assertEqual(execution.verdict, VerdictValeur.ECHOUE)
        self.assertIn("CMP-REJEU", preuve.campagne_id)

    def test_chemin_de_preuve(self):
        self.assertEqual(chemin_preuve("CMP-1", "A1"),
                         "preuves-locales/CMP-1/A1-rejeu.json")

    def test_fermeture_avec_preuve(self):
        cible = CibleFictive()
        cible.ajouter_garde_fou("remuneration")
        decouverte = finding()
        execution, preuve = self.rejeu(cible=cible)
        fermer(decouverte, preuve, execution)
        self.assertEqual(decouverte.statut, StatutFinding.FERME)
        self.assertEqual(decouverte.ferme_le, INSTANT)
        self.assertIn(preuve.id, decouverte.preuve_fermeture_ids)

    def test_fermeture_refusee_si_encore_ouvert(self):
        decouverte = finding()
        execution, preuve = self.rejeu()
        fermer(decouverte, preuve, execution)
        self.assertEqual(decouverte.statut, StatutFinding.OUVERT)
        self.assertEqual(decouverte.preuve_fermeture_ids, [])

    def test_technique_introuvable(self):
        from piege.erreurs import TechniqueInconnue

        with self.assertRaises(TechniqueInconnue):
            rejouer(finding(), CibleFictive(), mandat_valide(), 7)

    def test_depuis_le_catalogue(self):
        execution, _ = self.rejeu(technique=None,
                                  catalogue={"A1": technique_a1()})
        self.assertEqual(execution.technique_id, "A1")


class TestControles(unittest.TestCase):
    """R12 : effet de bord signalé dans la même ligne que la fermeture."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def execution(self, technique_id, verdict=VerdictValeur.ECHOUE, erreur=""):
        return Execution(id="EXE-1", campagne_id="CMP-1",
                         technique_id=technique_id, application_id="APP",
                         tenant_id="TEN", statut="execute", sondes_envoyees=["s"],
                         reponse_brute="r", jetons=10, latence_ms=1,
                         verdict=verdict, impact=1, confiance=0.9, citation="c",
                         motif="m", garde_fou_declenche=False, revue_humaine=False,
                         graine=1, erreur=erreur)

    def test_aucune_regression(self):
        self.assertEqual(controler_regression(finding(), [self.execution("A1")]), [])

    def test_regression_detectee(self):
        execu = self.execution("C1", verdict=VerdictValeur.REUSSI)
        self.assertEqual(controler_regression(finding(), [execu]), ["C1"])

    def test_refus_de_passerelle_pas_une_reussite(self):
        execu = self.execution("C1", verdict=VerdictValeur.REUSSI,
                               erreur="hors_perimetre")
        self.assertEqual(controler_regression(finding(), [execu]), [])

    def test_effet_de_bord_degrade(self):
        avant = [faux_refus("R-%d" % i) for i in range(31)]
        apres = [faux_refus("R-%d" % i) for i in range(34)]
        comparaison = controler_effet_de_bord(avant, apres)
        self.assertEqual(comparaison["delta"], 3)
        self.assertTrue(comparaison["signale"])
        self.assertEqual(len(comparaison["nouveaux_refus"]), 3)

    def test_effet_de_bord_neutre(self):
        avant = [faux_refus("R-1")]
        comparaison = controler_effet_de_bord(avant, avant)
        self.assertFalse(comparaison["signale"])
        self.assertIn("aucun", phrase_effet_de_bord(comparaison))

    def test_effet_de_bord_ameliore(self):
        comparaison = controler_effet_de_bord([faux_refus("R-1")], [])
        self.assertTrue(comparaison["amelioration"])
        self.assertIn("retrouvées", phrase_effet_de_bord(comparaison))

    def test_phrase_degradee(self):
        comparaison = controler_effet_de_bord([faux_refus("R-1")],
                                              [faux_refus("R-1"), faux_refus("R-2")])
        phrase = phrase_effet_de_bord(comparaison)
        self.assertIn("+1", phrase)
        self.assertIn("R-2", phrase)

    def test_ligne_de_fermeture_complete(self):
        cible = CibleFictive()
        cible.ajouter_garde_fou("remuneration")
        decouverte = finding()
        execution, preuve = rejouer(decouverte, cible, mandat_valide(), 7,
                                    technique=technique_a1(), juge=JugeFictif())
        comparaison = controler_effet_de_bord([faux_refus("R-1")],
                                              [faux_refus("R-1"), faux_refus("R-2")])
        ligne = fermeture_complete(decouverte, execution, comparaison, ["C1"])
        self.assertIn("FINDING-2026-0147", ligne)
        self.assertIn("+1", ligne)
        self.assertIn("C1", ligne)


class TestBoucleComplete(unittest.TestCase):
    """La boucle complète, du finding à la ligne de fermeture."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def lancer(self, cible=None, role="commanditaire", **kw):
        valeurs = dict(finding=finding(), cible=cible or CibleFictive(),
                       mandat=mandat_valide(), graine=7, auteur="anne.rssi",
                       role=role, technique=technique_a1(), juge=JugeFictif(),
                       faux_refus_avant=[faux_refus("R-%d" % i) for i in range(31)],
                       faux_refus_apres=[faux_refus("R-%d" % i) for i in range(34)])
        valeurs.update(kw)
        return boucle_complete(**valeurs)

    def test_boucle_nominale(self):
        bilan = self.lancer()
        self.assertIsInstance(bilan, BilanCorrection)
        self.assertTrue(bilan.autorise)
        self.assertTrue(bilan.applique)
        self.assertTrue(bilan.ferme)
        self.assertIsNotNone(bilan.preuve)

    def test_ligne_de_fermeture(self):
        bilan = self.lancer()
        self.assertIn("fermé", bilan.ligne)
        self.assertIn("faux refus 31", bilan.ligne)

    def test_effet_de_bord_sur_le_correctif(self):
        bilan = self.lancer()
        self.assertIn("+3", bilan.correctif.effet_de_bord)
        self.assertEqual(bilan.effet_de_bord["delta"], 3)

    def test_sans_accord_humain(self):
        bilan = self.lancer(role="proprietaire")
        self.assertFalse(bilan.autorise)
        self.assertFalse(bilan.applique)
        self.assertFalse(bilan.ferme)
        self.assertTrue(bilan.motifs)

    def test_correctif_insuffisant(self):
        """Un correctif qui ne bloque rien laisse la découverte ouverte."""
        class CibleSourde(CibleFictive):
            def ajouter_garde_fou(self, theme):
                pass

        bilan = self.lancer(cible=CibleSourde())
        self.assertTrue(bilan.applique)
        self.assertFalse(bilan.ferme)
        self.assertTrue(any("insuffisant" in m for m in bilan.motifs))

    def test_decouverte_fermee_en_base(self):
        decouverte = finding()
        self.lancer(finding=decouverte)
        self.assertEqual(decouverte.statut, StatutFinding.FERME)
        self.assertTrue(decouverte.correctif_ids)

    def test_sans_faux_refus(self):
        bilan = self.lancer(faux_refus_avant=None, faux_refus_apres=None)
        self.assertEqual(bilan.effet_de_bord, {})
        self.assertTrue(bilan.ferme)


class TestCampagneDeRejeu(unittest.TestCase):
    """Le rejeu produit une campagne distincte et traçable."""

    def test_campagne_de_rejeu(self):
        fixer_horloge(INSTANT)
        try:
            cible = CibleFictive()
            cible.ajouter_garde_fou("remuneration")
            execution, preuve = rejouer(finding(), cible, mandat_valide(), 7,
                                        technique=technique_a1(), juge=JugeFictif())
            self.assertEqual(execution.campagne_id, "CMP-REJEU-0147")
            self.assertEqual(preuve.campagne_id, "CMP-REJEU-0147")
            self.assertEqual(preuve.type, "rejeu")
        finally:
            fixer_horloge(None)

    def test_types_de_campagne_utilises(self):
        campagne = Campagne(id="CMP-1", mandat_id="MAN-1", application_id="APP",
                            tenant_id="TEN", type=TypeCampagne.REJEU, graine=1,
                            statut=StatutCampagne.TERMINEE)
        self.assertEqual(campagne.type, TypeCampagne.REJEU)

    def test_mandat_de_rejeu_valide(self):
        self.assertEqual(mandat_valide().statut, StatutMandat.VALIDE)
        self.assertEqual(application_demo().exposition, 2)

if __name__ == "__main__":
    unittest.main()
