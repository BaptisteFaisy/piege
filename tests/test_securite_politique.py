"""Tests de la politique de périmètre : R4, R10, production, budget, arrêt."""

from __future__ import annotations

import unittest

from piege.erreurs import (ArretUrgence, AutorisationHumaineAbsente,
                           BudgetEpuise, HorsPerimetre, MandatExpire,
                           ProductionInterdite)
from piege.securite import politique
from piege.types import Environnement, ProductionAutorisee, fixer_horloge

from doubles import APPLICATION, INSTANT, TENANT, application, campagne, mandat
from doubles import technique


def faits(**remplacements) -> dict:
    """Jeu de faits autorisé par défaut (sonde A1 sur la cible de démo)."""
    base = politique.faits_pour(mandat(), technique(), application(), campagne(),
                                maintenant=INSTANT)
    base.update(remplacements)
    return base


class TestAutorisation(unittest.TestCase):
    """Cas nominal : tout est dans le périmètre, la sonde est autorisée."""

    def tearDown(self):
        fixer_horloge(None)

    def test_sonde_autorisee(self):
        decision = politique.evaluer(politique.OUTIL_SONDE, faits())
        self.assertTrue(decision.accorde)
        self.assertEqual(decision.regle, "autorise")
        self.assertEqual(decision.code, "")

    def test_exiger_depuis_les_enregistrements(self):
        decision = politique.exiger(mandat(), technique(), application(),
                                    campagne(), maintenant=INSTANT)
        self.assertTrue(decision.accorde)

    def test_faits_contiennent_le_tenant(self):
        self.assertEqual(faits()["tenant_id"], TENANT)


class TestPerimetre(unittest.TestCase):
    """R4 : une cible ou une technique hors périmètre est refusée."""

    def test_cible_hors_perimetre(self):
        decision = politique.evaluer(politique.OUTIL_SONDE,
                                     faits(cible_id="APP-autre"))
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.code, "hors_perimetre")
        self.assertEqual(decision.regle, "perimetre.application")

    def test_technique_hors_perimetre(self):
        decision = politique.evaluer(politique.OUTIL_SONDE,
                                     faits(technique_id="D1"))
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.regle, "perimetre.technique")

    def test_environnement_non_couvert(self):
        decision = politique.evaluer(
            politique.OUTIL_SONDE,
            faits(cible_environnement=Environnement.PROD.value,
                  mandat_environnements=[Environnement.TEST.value]))
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.regle, "perimetre.environnement")

    def test_technique_ne_couvre_pas_lenvironnement(self):
        decision = politique.evaluer(
            politique.OUTIL_SONDE,
            faits(cible_environnement=Environnement.PREPROD.value,
                  technique_environnement=[Environnement.TEST.value]))
        self.assertEqual(decision.regle, "perimetre.technique.environnement")

    def test_mandat_expire(self):
        decision = politique.evaluer(politique.OUTIL_SONDE,
                                     faits(maintenant="2027-01-01T00:00:00Z"))
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.code, "mandat_expire")

    def test_mandat_non_valide(self):
        decision = politique.evaluer(politique.OUTIL_SONDE,
                                     faits(mandat_statut="brouillon"))
        self.assertEqual(decision.code, "mandat_invalide")


class TestProduction(unittest.TestCase):
    """Le catalogue prime le mandat : `jamais` n'est jamais levé."""

    def base_prod(self, **remplacements):
        valeurs = dict(cible_environnement=Environnement.PROD.value,
                       mandat_environnements=[Environnement.PROD.value],
                       technique_environnement=[Environnement.PROD.value])
        valeurs.update(remplacements)
        return politique.evaluer(politique.OUTIL_SONDE, faits(**valeurs))

    def test_interdite_par_le_catalogue(self):
        decision = self.base_prod(
            technique_production=ProductionAutorisee.JAMAIS.value,
            production_autorisee=True)
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.regle, "production.catalogue")

    def test_interdite_par_le_mandat(self):
        decision = self.base_prod(production_autorisee=False)
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.regle, "production.mandat")

    def test_autorisee_sur_mandat(self):
        decision = self.base_prod(production_autorisee=True)
        self.assertTrue(decision.accorde)

    def test_hors_production_sans_effet(self):
        decision = politique.evaluer(
            politique.OUTIL_SONDE,
            faits(technique_production=ProductionAutorisee.JAMAIS.value))
        self.assertTrue(decision.accorde)


class TestBudgetEtArret(unittest.TestCase):
    """ENF-02 et ENF-14 : budget plafonné, arrêt d'urgence immédiat."""

    def test_appels_epuises(self):
        decision = politique.evaluer(politique.OUTIL_SONDE,
                                     faits(campagne_appels_restants=0))
        self.assertEqual(decision.code, "budget_epuise")

    def test_jetons_insuffisants(self):
        decision = politique.evaluer(
            politique.OUTIL_SONDE,
            faits(campagne_jetons_restants=100, technique_budget_jetons=1500))
        self.assertEqual(decision.regle, "budget.jetons")

    def test_arret_urgence(self):
        decision = politique.evaluer(politique.OUTIL_SONDE,
                                     faits(arret_urgence=True))
        self.assertEqual(decision.code, "arret_urgence")

    def test_arret_prime_le_perimetre(self):
        """Ordre normatif : le budget et l'arrêt viennent après le périmètre."""
        decision = politique.evaluer(
            politique.OUTIL_SONDE,
            faits(cible_id="APP-autre", arret_urgence=True))
        self.assertEqual(decision.code, "hors_perimetre")


class TestCorrectif(unittest.TestCase):
    """R10 : un correctif sans accord humain explicite est refusé (EF-42)."""

    def evaluer(self, **remplacements):
        base = dict(correctif_autorisation_humaine=True,
                    correctif_autorise_par="commanditaire",
                    correctif_type="garde_fou")
        base.update(remplacements)
        return politique.evaluer(politique.OUTIL_GARDE_APPLIQUE, faits(**base))

    def test_sans_accord(self):
        decision = self.evaluer(correctif_autorisation_humaine=False)
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.code, "autorisation_absente")

    def test_role_non_habilite(self):
        decision = self.evaluer(correctif_autorise_par="proprietaire")
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.regle, "correctif.role")

    def test_analyste_habilite(self):
        self.assertTrue(self.evaluer(correctif_autorise_par="analyste").accorde)

    def test_types_interdits(self):
        for interdiction in ("prompt", "document", "code", "corpus"):
            decision = self.evaluer(correctif_type=interdiction)
            self.assertFalse(decision.accorde, interdiction)

    def test_proposition_libre(self):
        decision = politique.evaluer(politique.OUTIL_GARDE_PROPOSE, faits())
        self.assertTrue(decision.accorde)


class TestDepot(unittest.TestCase):
    """EF-17 : le dépôt de la famille F ne vise que l'index de test."""

    def evaluer(self, **remplacements):
        base = dict(index_cible="idx-test-1", index_de_test="idx-test-1",
                    index_production="idx-prod-1", depot_production=False)
        base.update(remplacements)
        return politique.evaluer(politique.OUTIL_DEPOT, faits(**base))

    def test_index_de_test_autorise(self):
        self.assertTrue(self.evaluer().accorde)

    def test_index_production_refuse(self):
        decision = self.evaluer(index_cible="idx-prod-1")
        self.assertFalse(decision.accorde)
        self.assertEqual(decision.regle, "depot.index")

    def test_index_production_sur_mandat_explicite(self):
        decision = self.evaluer(index_cible="idx-prod-1", depot_production=True)
        self.assertTrue(decision.accorde)


class TestLeveeDeRefus(unittest.TestCase):
    """`lever_refus` traduit une décision en exception de domaine."""

    def test_accord_ne_leve_rien(self):
        politique.lever_refus(politique.evaluer(politique.OUTIL_SONDE, faits()))

    def test_codes_traduits(self):
        attendus = {"hors_perimetre": HorsPerimetre, "budget_epuise": BudgetEpuise,
                    "arret_urgence": ArretUrgence,
                    "autorisation_absente": AutorisationHumaineAbsente,
                    "production_interdite": ProductionInterdite,
                    "mandat_expire": MandatExpire}
        for code, classe in attendus.items():
            decision = politique.refus(code, code, "motif", "outil", {})
            with self.assertRaises(classe):
                politique.lever_refus(decision)

    def test_details_portent_la_regle(self):
        decision = politique.evaluer(politique.OUTIL_SONDE,
                                     faits(cible_id="APP-autre"))
        try:
            politique.lever_refus(decision)
            self.fail("refus attendu")
        except HorsPerimetre as erreur:
            self.assertEqual(erreur.details["regle"], "perimetre.application")
            self.assertEqual(erreur.vers_dict()["erreur"]["code"], "hors_perimetre")

    def test_application_hors_mandat_depuis_les_enregistrements(self):
        autre = application(id="APP-autre")
        decision = politique.exiger(mandat(), technique(), autre, campagne(),
                                    maintenant=INSTANT)
        self.assertFalse(decision.accorde)


if __name__ == "__main__":
    unittest.main()
