"""Tests des mandats : R1 (aucun mandat), R2 (mandat expiré), signature."""

from __future__ import annotations

import unittest

from piege.erreurs import MandatExpire, MandatInvalide, ValeurHorsPlage
from piege.securite import mandats
from piege.types import Environnement, StatutMandat, fixer_horloge

from doubles import INSTANT, APPLICATION, TENANT


def brouillon(**remplacements):
    """Mandat en brouillon, non signé, sur la cible de démonstration."""
    valeurs = dict(
        tenant_id=TENANT, application_id=APPLICATION,
        perimetre_techniques=["A1", "F3"],
        environnements=[Environnement.TEST],
        fenetre_debut="2026-11-01T00:00:00Z", fenetre_fin="2026-12-01T00:00:00Z",
        budget_appels=288, budget_jetons=2_000_000, production_autorisee=False,
        contact_urgence="securite@client.example")
    valeurs.update(remplacements)
    return mandats.creer(**valeurs)


class TestCreation(unittest.TestCase):
    """Un mandat naît en brouillon : il ne peut rien autoriser."""

    def tearDown(self):
        fixer_horloge(None)

    def test_brouillon_inexploitable(self):
        self.assertEqual(brouillon().statut, StatutMandat.BROUILLON)
        with self.assertRaises(MandatInvalide):
            mandats.valider(brouillon(), INSTANT)

    def test_identifiant_horodate(self):
        self.assertEqual(brouillon().id, "MAN-2026-0001")
        self.assertEqual(brouillon(sequence=7).id, "MAN-2026-0007")

    def test_perimetre_trie_et_deduplique(self):
        mandat = brouillon()
        self.assertEqual(mandat.perimetre_techniques, ["A1", "F3"])
        autre = mandats.creer(
            tenant_id=TENANT, application_id=APPLICATION,
            perimetre_techniques=["F3", "A1", "F3"],
            environnements=[Environnement.TEST],
            fenetre_debut="2026-11-01T00:00:00Z",
            fenetre_fin="2026-12-01T00:00:00Z", budget_appels=10,
            budget_jetons=1000, production_autorisee=False, contact_urgence="x")
        self.assertEqual(autre.perimetre_techniques, ["A1", "F3"])

    def test_budget_nul_refuse(self):
        with self.assertRaises(ValeurHorsPlage):
            brouillon(budget_appels=0)
        with self.assertRaises(ValeurHorsPlage):
            brouillon(budget_jetons=-1)

    def test_fenetre_inversee_refusee(self):
        with self.assertRaises(ValeurHorsPlage):
            mandats.creer(
                tenant_id=TENANT, application_id=APPLICATION,
                perimetre_techniques=["A1"], environnements=[Environnement.TEST],
                fenetre_debut="2026-12-01T00:00:00Z",
                fenetre_fin="2026-11-01T00:00:00Z", budget_appels=10,
                budget_jetons=1000, production_autorisee=False,
                contact_urgence="x")


class TestSignature(unittest.TestCase):
    """La signature rend toute modification du périmètre détectable."""

    def tearDown(self):
        fixer_horloge(None)

    def test_signer_rend_valide(self):
        mandat = mandats.signer(brouillon())
        self.assertEqual(mandat.statut, StatutMandat.VALIDE)
        self.assertTrue(mandat.signature.startswith("sha256:"))
        self.assertTrue(mandats.signature_valide(mandat))

    def test_perimetre_modifie_apres_signature(self):
        mandat = mandats.signer(brouillon())
        mandat.perimetre_techniques = ["A1", "F3", "D1"]
        self.assertFalse(mandats.signature_valide(mandat))
        with self.assertRaises(MandatInvalide):
            mandats.valider(mandat, INSTANT)

    def test_budget_modifie_apres_signature(self):
        mandat = mandats.signer(brouillon())
        mandat.budget_appels = 100_000
        with self.assertRaises(MandatInvalide):
            mandats.valider(mandat, INSTANT)

    def test_signature_absente_non_bloquante(self):
        """Un mandat marqué valide sans signature reste contrôlé sur son statut."""
        mandat = brouillon()
        mandat.statut = StatutMandat.VALIDE
        self.assertEqual(mandats.valider(mandat, INSTANT), mandat)


class TestValidite(unittest.TestCase):
    """R1 et R2 du chapitre 30.2."""

    def tearDown(self):
        fixer_horloge(None)

    def test_r1_aucun_mandat(self):
        with self.assertRaises(MandatInvalide) as ctx:
            mandats.valider(None)
        self.assertEqual(ctx.exception.code, "mandat_invalide")

    def test_r2_mandat_expire(self):
        mandat = mandats.signer(brouillon())
        with self.assertRaises(MandatExpire) as ctx:
            mandats.valider(mandat, "2026-12-02T00:00:01Z")
        self.assertEqual(ctx.exception.code, "mandat_expire")

    def test_mandat_pas_encore_valide(self):
        mandat = mandats.signer(brouillon())
        with self.assertRaises(MandatExpire):
            mandats.valider(mandat, "2026-10-31T23:59:59Z")

    def test_dans_la_fenetre(self):
        mandat = mandats.signer(brouillon())
        self.assertEqual(mandats.valider(mandat, INSTANT), mandat)

    def test_revoque(self):
        mandat = mandats.signer(brouillon())
        mandat.statut = StatutMandat.REVOQUE
        with self.assertRaises(MandatInvalide):
            mandats.valider(mandat, INSTANT)

    def test_est_expire_sans_horloge_externe(self):
        mandat = mandats.signer(brouillon())
        self.assertTrue(mandats.est_expire(mandat, "2027-01-01T00:00:00Z"))
        self.assertFalse(mandats.est_expire(mandat, INSTANT))

    def test_contenu_canonique_stable(self):
        mandat = brouillon()
        self.assertEqual(mandats.contenu_canonique(mandat),
                         mandats.contenu_canonique(brouillon()))


if __name__ == "__main__":
    unittest.main()
