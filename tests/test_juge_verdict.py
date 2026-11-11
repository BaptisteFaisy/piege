"""Tests de l'appel du juge : verdict structuré, essais, invite fixe."""

from __future__ import annotations

import unittest

from piege.agents.juge import prompts
from piege.agents.juge.juge import juger, sortie_brute
from piege.erreurs import FournisseurIndisponible
from piege.types import VerdictValeur

from doubles_juge import FournisseurDouble, sortie, technique


class TestVerdict(unittest.TestCase):
    """Le verdict rendu porte tous les champs du contrat."""

    def test_champs_complets(self):
        fournisseur = FournisseurDouble([sortie()])
        verdict = juger(technique(), "transcription", fournisseur, graine=7,
                        modele="modele-fort")
        self.assertEqual(verdict.verdict, VerdictValeur.REUSSI)
        self.assertEqual(verdict.impact, 4)
        self.assertEqual(verdict.confiance, 0.93)
        self.assertEqual(verdict.graine, 7)
        self.assertEqual(verdict.modele, "modele-fort")
        self.assertEqual(verdict.version_invite, prompts.VERSION_INVITE)
        self.assertFalse(verdict.revue_humaine)

    def test_serialisable(self):
        fournisseur = FournisseurDouble([sortie()])
        verdict = juger(technique(), "t", fournisseur, graine=1)
        donnees = verdict.vers_dict()
        self.assertEqual(donnees["verdict"], "reussi")
        self.assertEqual(donnees["impact"], 4)

    def test_un_seul_appel_en_cas_de_succes(self):
        fournisseur = FournisseurDouble([sortie()])
        juger(technique(), "t", fournisseur, graine=1)
        self.assertEqual(len(fournisseur.appels), 1)

    def test_ambigu_sans_citation(self):
        fournisseur = FournisseurDouble([sortie(verdict="ambigu", impact=None,
                                                citation="", confiance=0.3)])
        verdict = juger(technique(), "t", fournisseur, graine=1)
        self.assertEqual(verdict.verdict, VerdictValeur.AMBIGU)
        self.assertIsNone(verdict.impact)


class TestInvite(unittest.TestCase):
    """L'invite est fixe, versionnée, et porte le critère de la technique."""

    def test_messages_construits(self):
        messages = prompts.construire(technique(), "TRANSCRIPTION")
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertIn("impact", messages[0]["content"])
        self.assertIn("A1", messages[1]["content"])
        self.assertIn("TRANSCRIPTION", messages[1]["content"])

    def test_critere_de_succes_inclus(self):
        messages = prompts.construire(
            technique(critere="la reponse cite le document depose"), "x")
        self.assertIn("la reponse cite le document depose", messages[1]["content"])

    def test_second_passage_independant(self):
        simple = prompts.construire(technique(), "x")
        second = prompts.construire(technique(), "x", second_passage=True)
        self.assertNotEqual(simple[0]["content"], second[0]["content"])
        self.assertIn("indépendant", second[0]["content"])

    def test_aucun_outil_dans_l_invite(self):
        """Le juge n'a aucun outil : l'invite ne peut pas en déclarer."""
        messages = prompts.construire(technique(), "x")
        for message in messages:
            self.assertNotIn("tool", message)
            self.assertNotIn("function_call", message)

    def test_version_d_invite_stable(self):
        self.assertEqual(prompts.VERSION_INVITE, "juge-1.0")

    def test_transmis_au_fournisseur(self):
        fournisseur = FournisseurDouble([sortie()])
        sortie_brute(technique(), "t", fournisseur, 3)
        self.assertEqual(fournisseur.appels[0]["graine"], 3)
        self.assertIn("properties", fournisseur.appels[0]["schema"])


class TestEssais(unittest.TestCase):
    """Une sortie invalide est rejouée une fois, puis l'erreur remonte."""

    def test_reussite_au_second_essai(self):
        fournisseur = FournisseurDouble([{"verdict": "inconnu"}, sortie()])
        verdict = juger(technique(), "t", fournisseur, graine=5)
        self.assertEqual(verdict.verdict, VerdictValeur.REUSSI)
        self.assertEqual(len(fournisseur.appels), 2)

    def test_graines_distinctes_entre_essais(self):
        fournisseur = FournisseurDouble([{"verdict": "inconnu"}, sortie()])
        juger(technique(), "t", fournisseur, graine=5)
        self.assertEqual([a["graine"] for a in fournisseur.appels], [5, 6])

    def test_echec_apres_deux_essais(self):
        fournisseur = FournisseurDouble([{"verdict": "x"}, {"verdict": "y"}])
        with self.assertRaises(FournisseurIndisponible):
            juger(technique(), "t", fournisseur, graine=1)
        self.assertEqual(len(fournisseur.appels), 2)

    def test_essai_max_parametrable(self):
        fournisseur = FournisseurDouble([{}] * 5)
        with self.assertRaises(FournisseurIndisponible):
            juger(technique(), "t", fournisseur, graine=1, essai_max=3)
        self.assertEqual(len(fournisseur.appels), 3)

    def test_fournisseur_absent(self):
        with self.assertRaises(FournisseurIndisponible) as ctx:
            juger(technique(), "t", None, graine=1)
        self.assertEqual(ctx.exception.details["regle"], "juge.fournisseur")


if __name__ == "__main__":
    unittest.main()
