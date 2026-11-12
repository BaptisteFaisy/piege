"""Tests des fournisseurs de modèle : local déterministe, InferHub injecté."""

from __future__ import annotations

import json
import os
import unittest

from piege.erreurs import FournisseurIndisponible
from piege.fournisseurs import creer_fournisseur
from piege.fournisseurs.base import NOMS, ReponseModele
from piege.fournisseurs.inferhub import (MODELE_DEFAUT, URL_DEFAUT,
                                         extraire_json)
from piege.fournisseurs.local import (FournisseurLocal, estimer_jetons,
                                       extraire_transcription)


class TestFabrique(unittest.TestCase):
    """La fabrique choisit l'implémentation, et refuse l'inconnu."""

    def test_noms_publies(self):
        self.assertEqual(NOMS, ("local", "inferhub", "openai", "bedrock"))

    def test_local_par_defaut(self):
        self.assertIsInstance(creer_fournisseur(), FournisseurLocal)

    def test_nom_explicite(self):
        self.assertEqual(creer_fournisseur("local").nom, "local")

    def test_openai_est_le_client_compatible(self):
        """`openai` vise le client OpenAI-compatible — endpoint libre compris."""
        self.assertEqual(creer_fournisseur("openai").nom, "inferhub")

    def test_inconnu(self):
        with self.assertRaises(ValueError):
            creer_fournisseur("inconnu")


class TestFournisseurLocal(unittest.TestCase):
    """Le fournisseur local est déterministe et ne fait aucun réseau."""

    def test_completion_deterministe(self):
        fournisseur = FournisseurLocal()
        messages = [{"role": "user", "content": "bonjour"}]
        premier = fournisseur.completer(messages, graine=7)
        second = fournisseur.completer(messages, graine=7)
        self.assertEqual(premier.texte, second.texte)
        self.assertIsInstance(premier, ReponseModele)

    def test_jetons_declares(self):
        fournisseur = FournisseurLocal()
        reponse = fournisseur.completer([{"role": "user", "content": "x" * 400}],
                                         graine=1)
        self.assertGreater(reponse.jetons_entree, 0)
        self.assertGreater(reponse.jetons_sortie, 0)

    def test_graine_change_reponse(self):
        fournisseur = FournisseurLocal()
        messages = [{"role": "user", "content": "bonjour"}]
        reponses = {fournisseur.completer(messages, graine=g).texte
                    for g in range(12)}
        self.assertGreater(len(reponses), 1)

    def test_classificateur_injecte(self):
        def classer(transcription):
            return {"verdict": "echoue", "impact": 1, "citation": "",
                    "confiance": 0.5, "motif": "test", "garde_fou_declenche": True}

        fournisseur = FournisseurLocal(classificateur=classer)
        sortie = fournisseur.sortie_structuree([{"role": "user", "content": "x"}],
                                                {"type": "object"}, 1)
        self.assertEqual(sortie["verdict"], "echoue")
        self.assertTrue(sortie["garde_fou_declenche"])

    def test_enum_normalisees(self):
        def classer(transcription):
            from piege.types import VerdictValeur

            return {"verdict": VerdictValeur.REUSSI, "impact": 4,
                    "citation": "x", "confiance": 0.9, "motif": "m",
                    "garde_fou_declenche": False}

        sortie = FournisseurLocal(classificateur=classer).sortie_structuree(
            [{"role": "user", "content": "x"}], {"type": "object"}, 1)
        self.assertEqual(sortie["verdict"], "reussi")

    def test_schema_invalide(self):
        with self.assertRaises(FournisseurIndisponible):
            FournisseurLocal().sortie_structuree([{"role": "user", "content": "x"}],
                                                  "pas-un-schema", 1)

    def test_estimation_jetons(self):
        self.assertEqual(estimer_jetons(""), 1)
        self.assertEqual(estimer_jetons("abcd" * 4), 4)

    def test_extraction_transcription(self):
        messages = [{"role": "user",
                     "content": "TRANSCRIPTION\n---\nla réponse\n---\n"}]
        self.assertEqual(extraire_transcription(messages).strip(), "la réponse")

    def test_extraction_absente(self):
        self.assertEqual(extraire_transcription([]), "")


class TestInferhub(unittest.TestCase):
    """Le client HTTP est exercé par un transport injecté : aucun réseau."""

    def fournisseur(self, reponse=None, cle="cle-test"):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        appels = []

        def transport(url, charge, cle_envoyee):
            appels.append({"url": url, "charge": charge, "cle": cle_envoyee})
            return reponse or {"choices": [{"message": {"content": "bonjour"}}],
                               "usage": {"prompt_tokens": 42,
                                         "completion_tokens": 7}}

        fournisseur = FournisseurInferhub(cle=cle, transport=transport)
        fournisseur.appels = appels
        return fournisseur

    def test_constantes(self):
        self.assertEqual(URL_DEFAUT,
                         "https://api.inferhub.dev/v1/chat/completions")
        self.assertEqual(MODELE_DEFAUT, "ag/gemini-3.8-flash-high")

    def test_completion(self):
        fournisseur = self.fournisseur()
        reponse = fournisseur.completer([{"role": "user", "content": "salut"}],
                                         graine=1)
        self.assertEqual(reponse.texte, "bonjour")
        self.assertEqual(reponse.jetons_entree, 42)
        self.assertEqual(reponse.jetons_sortie, 7)
        self.assertEqual(fournisseur.appels[0]["charge"]["model"],
                         MODELE_DEFAUT)
        self.assertEqual(fournisseur.appels[0]["cle"], "cle-test")

    def test_sortie_structuree(self):
        fournisseur = self.fournisseur(reponse={
            "choices": [{"message": {"content": '{"verdict": "reussi"}'}}]})
        sortie = fournisseur.sortie_structuree([{"role": "user", "content": "x"}],
                                                {"type": "object"}, 1)
        self.assertEqual(sortie["verdict"], "reussi")
        self.assertTrue(fournisseur.appels[0]["charge"]["response_format"])

    def test_absence_de_cle(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        fournisseur = FournisseurInferhub(cle="", transport=lambda *a: {})
        with self.assertRaises(FournisseurIndisponible) as ctx:
            fournisseur.completer([{"role": "user", "content": "x"}], 1)
        self.assertEqual(ctx.exception.details["regle"], "fournisseur.inferhub.cle")

    def test_reponse_illisible(self):
        fournisseur = self.fournisseur(reponse={"unexpected": True})
        with self.assertRaises(FournisseurIndisponible):
            fournisseur.completer([{"role": "user", "content": "x"}], 1)

    def test_erreur_transport(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        def transport(url, charge, cle):
            raise OSError("réseau injoignable")

        fournisseur = FournisseurInferhub(cle="k", transport=transport)
        with self.assertRaises(FournisseurIndisponible):
            fournisseur.completer([{"role": "user", "content": "x"}], 1)

    def test_extraire_json(self):
        self.assertEqual(extraire_json('{"a": 1}'), {"a": 1})
        self.assertEqual(extraire_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extraire_json('Voici : {"a": 1} — fin'), {"a": 1})

    def test_extraire_json_illisible(self):
        with self.assertRaises(FournisseurIndisponible):
            extraire_json("pas de json ici")
        with self.assertRaises(FournisseurIndisponible):
            extraire_json("")

    def test_cle_jamais_journalisee(self):
        """La clé n'apparaît dans aucune sortie de l'appel."""
        fournisseur = self.fournisseur(cle="cle-super-secrete")
        fournisseur.completer([{"role": "user", "content": "x"}], 1)
        self.assertNotIn("cle-super-secrete",
                         json.dumps(fournisseur.appels[0]["charge"]))


class TestBedrock(unittest.TestCase):
    """Sans boto3, le fournisseur Bedrock le dit clairement."""

    def test_sans_client(self):
        from piege.fournisseurs.bedrock import FournisseurBedrock

        try:
            import boto3                                    # noqa: F401,PLC0415
        except ImportError:
            pass
        else:
            self.skipTest("boto3 installé : le repli n'est pas exercé")
        fournisseur = FournisseurBedrock()
        with self.assertRaises(FournisseurIndisponible) as ctx:
            fournisseur.client()
        self.assertEqual(ctx.exception.details["regle"],
                         "fournisseur.bedrock.client")

    def test_avec_client_double(self):
        from piege.fournisseurs.bedrock import FournisseurBedrock

        class Client:
            def converse(self, **charge):
                return {"output": {"message": {"content": [
                    {"text": '{"verdict": "reussi"}'}]}},
                    "usage": {"inputTokens": 5, "outputTokens": 2}}

        fournisseur = FournisseurBedrock(client=Client())
        reponse = fournisseur.completer([{"role": "user", "content": "x"}], 1)
        self.assertEqual(reponse.jetons_entree, 5)
        sortie = fournisseur.sortie_structuree([{"role": "user", "content": "x"}],
                                                {"type": "object"}, 1)
        self.assertEqual(sortie["verdict"], "reussi")

    def test_variables_d_environnement(self):
        from piege.fournisseurs.bedrock import FournisseurBedrock

        os.environ["PIEGE_MODELE"] = "amazon.nova-pro-v1:0"
        try:
            self.assertEqual(FournisseurBedrock().modele, "amazon.nova-pro-v1:0")
        finally:
            os.environ.pop("PIEGE_MODELE", None)


if __name__ == "__main__":
    unittest.main()


class TestDelaiEtNouvellesTentatives(unittest.TestCase):
    """Mode réel : un appel lent ne doit pas faire échouer toute la campagne."""

    def test_delai_par_defaut(self):
        from piege.fournisseurs.inferhub import TIMEOUT_DEFAUT, FournisseurInferhub

        self.assertGreaterEqual(TIMEOUT_DEFAUT, 120)
        self.assertEqual(FournisseurInferhub(cle="k").timeout, TIMEOUT_DEFAUT)

    def test_delai_par_variable(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        os.environ["PIEGE_LLM_TIMEOUT"] = "240"
        try:
            self.assertEqual(FournisseurInferhub(cle="k").timeout, 240)
        finally:
            os.environ.pop("PIEGE_LLM_TIMEOUT", None)

    def test_delai_explicite_prioritaire(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        os.environ["PIEGE_LLM_TIMEOUT"] = "240"
        try:
            self.assertEqual(FournisseurInferhub(cle="k", timeout=30).timeout, 30)
        finally:
            os.environ.pop("PIEGE_LLM_TIMEOUT", None)

    def test_nouvelle_tentative_apres_timeout(self):
        """Un transport qui échoue puis répond : l'appel aboutit."""
        from piege.fournisseurs.inferhub import FournisseurInferhub
        from piege.erreurs import FournisseurIndisponible

        etat = {"n": 0}

        def transport(url, charge, cle):
            etat["n"] += 1
            if etat["n"] == 1:
                raise FournisseurIndisponible("read timed out",
                                              code="fournisseur_indisponible")
            return {"choices": [{"message": {"content": "bonjour"}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1}}

        fournisseur = FournisseurInferhub(cle="k", transport=transport,
                                          tentatives=2)
        reponse = fournisseur.completer([{"role": "user", "content": "x"}], 1)
        self.assertEqual(reponse.texte, "bonjour")
        self.assertEqual(etat["n"], 2)

    def test_tentatives_epuisees(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub
        from piege.erreurs import FournisseurIndisponible

        def transport(url, charge, cle):
            raise FournisseurIndisponible("read timed out",
                                          code="fournisseur_indisponible")

        fournisseur = FournisseurInferhub(cle="k", transport=transport,
                                          tentatives=3)
        with self.assertRaises(FournisseurIndisponible):
            fournisseur.completer([{"role": "user", "content": "x"}], 1)

    def test_une_seule_tentative_si_demande(self):
        from piege.fournisseurs.inferhub import FournisseurInferhub
        from piege.erreurs import FournisseurIndisponible

        appels = []

        def transport(url, charge, cle):
            appels.append(1)
            raise FournisseurIndisponible("ko", code="fournisseur_indisponible")

        with self.assertRaises(FournisseurIndisponible):
            FournisseurInferhub(cle="k", transport=transport,
                                tentatives=1).completer([{"role": "user",
                                                          "content": "x"}], 1)
        self.assertEqual(len(appels), 1)

    def test_cout_reel_capté(self):
        """Le coût renvoyé par le routeur alimente le KPI-7."""
        from piege.fournisseurs.inferhub import FournisseurInferhub

        def transport(url, charge, cle):
            return {"choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                              "cost": 0.00002,
                              "completion_tokens_details": {"reasoning_tokens": 4}}}

        reponse = FournisseurInferhub(cle="k", transport=transport).completer(
            [{"role": "user", "content": "x"}], 1)
        self.assertEqual(reponse.brut["cout"], 0.00002)
        self.assertEqual(reponse.brut["raisonnement"], 4)


class TestSortieEnTableau(unittest.TestCase):
    """Certains modèles renvoient `[{…}]` au lieu de `{…}` : on déshabille."""

    def fournisseur(self, contenu):
        from piege.fournisseurs.inferhub import FournisseurInferhub

        def transport(url, charge, cle):
            return {"choices": [{"message": {"content": contenu}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 5}}

        return FournisseurInferhub(cle="k", transport=transport)

    def test_tableau_a_un_objet(self):
        sortie = self.fournisseur('[{"verdict": "reussi", "impact": 4}]').\
            sortie_structuree([{"role": "user", "content": "x"}], {"type": "object"}, 1)
        self.assertEqual(sortie["verdict"], "reussi")

    def test_tableau_avec_bruit(self):
        contenu = '[{"autre": 1}, {"verdict": "echoue", "citation": ""}]'
        sortie = self.fournisseur(contenu).sortie_structuree(
            [{"role": "user", "content": "x"}], {"type": "object"}, 1)
        self.assertEqual(sortie["verdict"], "echoue")

    def test_tableau_inexploitable(self):
        from piege.erreurs import FournisseurIndisponible

        with self.assertRaises(FournisseurIndisponible):
            self.fournisseur("[1, 2, 3]").sortie_structuree(
                [{"role": "user", "content": "x"}], {"type": "object"}, 1)

    def test_tableau_enrobe_de_texte(self):
        from piege.fournisseurs.inferhub import extraire_json

        # Un tableau entouré de texte reste refusé : on ne devine pas.
        with self.assertRaises(FournisseurIndisponible):
            extraire_json("voici [1,2] et voilà")

    def test_objet_json_direct(self):
        from piege.fournisseurs.inferhub import objet_json

        self.assertEqual(objet_json({"a": 1}), {"a": 1})
        self.assertEqual(objet_json([{"a": 1}]), {"a": 1})
