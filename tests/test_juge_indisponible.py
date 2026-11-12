"""Tests de robustesse du jugement : un juge défaillant ne perd pas la campagne."""

from __future__ import annotations

import os
import unittest

from piege.correctifs.rejeu import est_ferme
from piege.erreurs import FournisseurIndisponible
from piege.moteur import executer_campagne
from piege.types import Execution, StatutCampagne, VerdictValeur, fixer_horloge

from doubles_moteur import (CibleDouble, EntrepotDouble, JournalDouble,
                            configuration_campagne, juge_double)

INSTANT = "2026-11-24T09:14:03Z"


def juge_en_panne(technique, transcription, fournisseur, graine):
    """Juge qui rend toujours une sortie inexploitable."""
    raise FournisseurIndisponible("sortie du modèle inexploitable : reçu list",
                                  code="fournisseur_indisponible",
                                  details={"regle": "juge.schema"})


def juge_selectif(panne_sur):
    """Juge qui échoue sur certaines techniques seulement."""
    def juge(technique_, transcription, fournisseur, graine):
        if technique_.id in panne_sur:
            raise FournisseurIndisponible("sortie illisible",
                                          code="fournisseur_indisponible")
        return juge_double()(technique_, transcription, fournisseur, graine)

    return juge


def execution(statut="execute", verdict=VerdictValeur.ECHOUE, erreur="",
              revue=False) -> Execution:
    """Exécution de test."""
    return Execution(id="EXE-1", campagne_id="CMP-1", technique_id="A1",
                     application_id="APP", tenant_id="TEN", statut=statut,
                     sondes_envoyees=["s"], reponse_brute="r", jetons=10,
                     latence_ms=1, verdict=verdict, impact=1, confiance=0.9,
                     citation="c", motif="m", garde_fou_declenche=False,
                     revue_humaine=revue, graine=1, erreur=erreur)


class TestJugeDefaillant(unittest.TestCase):
    """La campagne survit à un juge qui rend une sortie illisible."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_campagne_terminee_malgre_juge_hs(self):
        entrepot = EntrepotDouble()
        campagne = executer_campagne(
            configuration_campagne(juge=juge_en_panne, entrepot=entrepot))
        self.assertEqual(campagne.statut, StatutCampagne.TERMINEE)
        self.assertEqual(len(entrepot.lister("executions")), 3)

    def test_execution_marquee_en_revue(self):
        entrepot = EntrepotDouble()
        executer_campagne(
            configuration_campagne(juge=juge_en_panne, entrepot=entrepot))
        for brute in entrepot.lister("executions"):
            self.assertEqual(brute["statut"], "verdict_indisponible")
            self.assertIsNone(brute["verdict"])
            self.assertTrue(brute["revue_humaine"])
            self.assertIn("verdict illisible", brute["motif"])

    def test_aucune_decouverte_inventee(self):
        """Pas de verdict → pas de découverte : on ne devine jamais."""
        entrepot = EntrepotDouble()
        executer_campagne(
            configuration_campagne(juge=juge_en_panne, entrepot=entrepot))
        self.assertEqual(entrepot.lister("findings"), [])

    def test_panne_partielle(self):
        """Une technique en panne n'empêche pas les autres d'être jugées."""
        entrepot = EntrepotDouble()
        campagne = executer_campagne(
            configuration_campagne(juge=juge_selectif({"C1"}), entrepot=entrepot))
        self.assertEqual(campagne.statut, StatutCampagne.TERMINEE)
        par_technique = {e["technique_id"]: e for e in entrepot.lister("executions")}
        self.assertEqual(par_technique["C1"]["statut"], "verdict_indisponible")
        self.assertEqual(par_technique["A1"]["verdict"], "reussi")
        self.assertEqual(par_technique["C4"]["verdict"], "reussi")

    def test_sonde_toujours_envoyee(self):
        """L'attaque a bien eu lieu : seule la mesure du verdict a échoué."""
        cible = CibleDouble()
        executer_campagne(configuration_campagne(juge=juge_en_panne, cible=cible))
        self.assertEqual(len(cible.appels), 3)

    def test_journal_trace_l_incident(self):
        journal = JournalDouble()
        executer_campagne(configuration_campagne(juge=juge_en_panne, journal=journal))
        self.assertTrue(any(l["quoi"] == "verdict_indisponible"
                            for l in journal.lignes))

    def test_sondes_conservees_pour_rejeu(self):
        """La transcription reste disponible : un humain peut trancher."""
        entrepot = EntrepotDouble()
        executer_campagne(
            configuration_campagne(juge=juge_en_panne, entrepot=entrepot))
        brute = entrepot.lister("executions")[0]
        self.assertTrue(brute["sondes_envoyees"])
        self.assertTrue(brute["reponse_brute"])


class TestFermetureNonStatuee(unittest.TestCase):
    """Une absence de verdict ne prouve jamais une fermeture."""

    def test_echec_ferme(self):
        self.assertTrue(est_ferme(execution(verdict=VerdictValeur.ECHOUE)))

    def test_reussite_ouverte(self):
        self.assertFalse(est_ferme(execution(verdict=VerdictValeur.REUSSI)))

    def test_ambigu_ouvert(self):
        self.assertFalse(est_ferme(execution(verdict=VerdictValeur.AMBIGU)))

    def test_non_statue_ouvert(self):
        self.assertFalse(est_ferme(execution(statut="verdict_indisponible",
                                             verdict=None)))

    def test_refus_passerelle_ferme(self):
        self.assertTrue(est_ferme(execution(statut="refuse", verdict=None,
                                            erreur="hors_perimetre")))


class TestBudgetSortieJuge(unittest.TestCase):
    """Le budget de sortie du juge est configurable (modèles à raisonnement)."""

    def tearDown(self):
        os.environ.pop("PIEGE_LLM_MAX_JETONS", None)

    def test_defaut_large(self):
        from piege.fournisseurs.inferhub import (MAX_JETONS_SORTIE_DEFAUT,
                                                 FournisseurInferhub)

        self.assertGreaterEqual(MAX_JETONS_SORTIE_DEFAUT, 4000)
        self.assertEqual(FournisseurInferhub(cle="k").max_jetons_sortie,
                         MAX_JETONS_SORTIE_DEFAUT)

    def test_variable_environnement(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        os.environ["PIEGE_LLM_MAX_JETONS"] = "6000"
        self.assertEqual(FournisseurInferhub(cle="k").max_jetons_sortie, 6000)

    def test_argument_prioritaire(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        os.environ["PIEGE_LLM_MAX_JETONS"] = "6000"
        self.assertEqual(
            FournisseurInferhub(cle="k", max_jetons_sortie=2500).max_jetons_sortie,
            2500)

    def test_transmis_a_l_appel(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        vus = []

        def transport(url, charge, cle):
            vus.append(charge)
            return {"choices": [{"message": {"content": '{"verdict": "echoue", '
                                                 '"confiance": 0.9, "motif": "m"}'}}]}

        FournisseurInferhub(cle="k", transport=transport,
                            max_jetons_sortie=3210).sortie_structuree(
                                [{"role": "user", "content": "x"}], {}, 1)
        self.assertEqual(vus[0]["max_tokens"], 3210)


if __name__ == "__main__":
    unittest.main()
