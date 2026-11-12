"""Tests du diagnostic du juge : une sortie illisible doit rester explicable.

Rejeu réel du 2026-11-12 (campagne CMP-1337) : deux verdicts perdus avec pour
seule trace « `verdict` absent ». La cause était invisible — sortie coupée par
le budget de raisonnement, ou objet rendu avec d'autres clés. Ces tests fixent
les deux réponses : la troncature se rejoue à budget doublé, et toute erreur
remonte avec un extrait brut et les clés reçues.
"""

from __future__ import annotations

import unittest

from piege.agents.juge.schema import valider_sortie
from piege.erreurs import FournisseurIndisponible
from piege.fournisseurs.inferhub import (EXTRAIT_MAX, MAX_JETONS_PLAFOND,
                                         FournisseurInferhub, joindre_extrait,
                                         tronquee)
from piege.moteur import executer_campagne

from doubles_moteur import (EntrepotDouble, JournalDouble,
                            configuration_campagne)

OBJET_VALIDE = ('{"verdict": "reussi", "impact": 3, "citation": "extrait", '
                '"confiance": 0.9, "motif": "fuite", "garde_fou_declenche": false}')
COUPE = '{"verdict": "reuss'
MESSAGES = [{"role": "user", "content": "TRANSCRIPTION"}]


def reponse(contenu: str, fin: str = "stop") -> dict:
    """Réponse OpenAI-compatible minimale, avec son motif de fin."""
    return {"choices": [{"message": {"content": contenu}, "finish_reason": fin}]}


def fournisseur_programme(sorties, budget: int = 4000) -> FournisseurInferhub:
    """Fournisseur dont le transport rend les sorties prévues, dans l'ordre.

    `sorties` est une liste de couples `(contenu, finish_reason)` ; le dernier
    est répété. Les charges utiles envoyées sont mémorisées pour être asserties.
    """
    vus: list[dict] = []

    def transport(url, charge, cle):
        vus.append(charge)
        contenu, fin = sorties[min(len(vus) - 1, len(sorties) - 1)]
        return reponse(contenu, fin)

    fournisseur = FournisseurInferhub(cle="k", transport=transport,
                                      max_jetons_sortie=budget)
    fournisseur.charges_vues = vus
    return fournisseur


def budgets_vus(fournisseur: FournisseurInferhub) -> list:
    """Budgets de sortie successivement demandés au fournisseur."""
    return [charge["max_tokens"] for charge in fournisseur.charges_vues]


class TestSortieTronquee(unittest.TestCase):
    """Une sortie coupée par le budget est rejouée avec un budget doublé."""

    def test_relance_jusqu_a_un_objet_complet(self):
        fournisseur = fournisseur_programme([(COUPE, "length"), (OBJET_VALIDE, "stop")],
                                            budget=2000)
        objet = fournisseur.sortie_structuree(MESSAGES, {}, 1)
        self.assertEqual(objet["verdict"], "reussi")
        self.assertEqual(budgets_vus(fournisseur), [2000, 4000])

    def test_verdict_valide_apres_relance(self):
        """La sortie rejouée passe la validation stricte du lot 5."""
        fournisseur = fournisseur_programme([(COUPE, "length"), (OBJET_VALIDE, "stop")])
        objet = fournisseur.sortie_structuree(MESSAGES, {}, 1)
        self.assertEqual(valider_sortie(objet)["impact"], 3)

    def test_une_seule_relance_jusqu_au_plafond(self):
        fournisseur = fournisseur_programme([(COUPE, "length")], budget=8000)
        with self.assertRaises(FournisseurIndisponible):
            fournisseur.sortie_structuree(MESSAGES, {}, 1)
        self.assertEqual(budgets_vus(fournisseur), [8000, MAX_JETONS_PLAFOND])

    def test_plafond_jamais_depasse(self):
        fournisseur = fournisseur_programme([(COUPE, "length")],
                                            budget=MAX_JETONS_PLAFOND)
        with self.assertRaises(FournisseurIndisponible):
            fournisseur.sortie_structuree(MESSAGES, {}, 1)
        self.assertEqual(budgets_vus(fournisseur), [MAX_JETONS_PLAFOND])

    def test_pas_de_relance_si_sortie_complete(self):
        """Une sortie complète mais hors schéma n'est pas un problème de budget."""
        fournisseur = fournisseur_programme([("texte libre sans objet", "stop")])
        with self.assertRaises(FournisseurIndisponible):
            fournisseur.sortie_structuree(MESSAGES, {}, 1)
        self.assertEqual(len(fournisseur.charges_vues), 1)


class TestExtraitJoint(unittest.TestCase):
    """L'erreur remonte avec la sortie brute : la cause est lisible a posteriori."""

    def test_extrait_et_longueur_dans_details(self):
        brut = "du texte libre, aucun objet"
        fournisseur = fournisseur_programme([(brut, "stop")])
        with self.assertRaises(FournisseurIndisponible) as contexte:
            fournisseur.sortie_structuree(MESSAGES, {}, 1)
        self.assertEqual(contexte.exception.details["extrait"], brut)
        self.assertEqual(contexte.exception.details["longueur"], len(brut))

    def test_extrait_borne(self):
        long = "x" * (EXTRAIT_MAX * 3)
        erreur = joindre_extrait(FournisseurIndisponible("illisible"), long)
        self.assertEqual(len(erreur.details["extrait"]), EXTRAIT_MAX)
        self.assertEqual(erreur.details["longueur"], len(long))

    def test_details_existants_conserves(self):
        erreur = joindre_extrait(
            FournisseurIndisponible("illisible", details={"regle": "juge.schema"}),
            "{}")
        self.assertEqual(erreur.details["regle"], "juge.schema")

    def test_troncature_detectee(self):
        self.assertTrue(tronquee(reponse("", "length")))
        self.assertFalse(tronquee(reponse("", "stop")))
        self.assertFalse(tronquee(reponse("", "")))
        self.assertFalse(tronquee({}))


class TestSchemaExplicite(unittest.TestCase):
    """Un `verdict` absent dit quelles clés ont été reçues."""

    def test_cles_recues_dans_le_message(self):
        with self.assertRaises(FournisseurIndisponible) as contexte:
            valider_sortie({"decision": "reussi", "motif": "m"})
        self.assertIn("clés reçues", str(contexte.exception))
        self.assertIn("decision", str(contexte.exception))
        self.assertEqual(contexte.exception.details["cles"], ["decision", "motif"])

    def test_aucune_cle(self):
        with self.assertRaises(FournisseurIndisponible) as contexte:
            valider_sortie({})
        self.assertIn("aucune", str(contexte.exception))


def juge_illisible(technique, transcription, fournisseur, graine):
    """Juge dont la sortie est inexploitable, diagnostic du fournisseur inclus."""
    raise joindre_extrait(
        FournisseurIndisponible(
            "sortie du juge : `verdict` absent (clés reçues : decision)",
            code="fournisseur_indisponible",
            details={"regle": "juge.schema", "cles": ["decision"]}),
        '{"decision": "reussi"}')


class TestJournalDiagnostic(unittest.TestCase):
    """Le moteur journalise le diagnostic, pas seulement un motif tronqué."""

    def test_extrait_et_regle_journalises(self):
        journal = JournalDouble()
        executer_campagne(configuration_campagne(
            juge=juge_illisible, journal=journal, technique_ids=("A1",)))
        lignes = [l for l in journal.lignes if l["quoi"] == "verdict_indisponible"]
        self.assertEqual(len(lignes), 1)
        details = lignes[0]["details"]
        self.assertEqual(details["extrait"], '{"decision": "reussi"}')
        self.assertEqual(details["regle"], "juge.schema")
        self.assertEqual(details["cles"], ["decision"])

    def test_motif_court_mais_explicite(self):
        entrepot = EntrepotDouble()
        executer_campagne(configuration_campagne(
            juge=juge_illisible, entrepot=entrepot, technique_ids=("A1",)))
        execution = entrepot.lister("executions")[0]
        self.assertEqual(execution["statut"], "verdict_indisponible")
        self.assertIn("verdict illisible", execution["motif"])
        self.assertLessEqual(len(execution["motif"]), len("verdict illisible : ") + 160)

    def test_campagne_toujours_terminee(self):
        """Le diagnostic ne change rien à la robustesse déjà acquise (lot 3)."""
        campagne = executer_campagne(configuration_campagne(
            juge=juge_illisible, technique_ids=("A1", "C1")))
        self.assertEqual(campagne.statut.value, "terminee")


if __name__ == "__main__":
    unittest.main()
