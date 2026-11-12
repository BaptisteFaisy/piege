"""Tests du câblage « mode vrai modèle » : interrupteurs d'environnement."""

from __future__ import annotations

import os
import tempfile
import unittest

from piege.api.contexte import creer_api
from piege.api.routeur import router
from piege.cibles.inferhub import CibleInferhub
from piege.types import Environnement, fixer_horloge

INSTANT = "2026-11-24T09:14:03Z"
JETON = "jeton:TEN-acme:commanditaire:analyste"
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(RACINE, "demo", "corpus")


class FournisseurDouble:
    """Fournisseur de modèle programmable (aucun réseau)."""

    nom = "double"

    def completer(self, messages, graine, max_jetons=1500, temperature=0.0):
        from piege.fournisseurs.base import ReponseModele

        return ReponseModele(texte="réponse du modèle", jetons_entree=100,
                             jetons_sortie=20, modele="double",
                             brut={"cout": 0.00001})

    def sortie_structuree(self, messages, schema, graine):
        return {"verdict": "echoue", "impact": 1, "citation": "",
                "confiance": 0.9, "motif": "double", "garde_fou_declenche": False}


class BaseModeReel(unittest.TestCase):
    """Contexte d'API isolé avec cible réelle à fournisseur injecté."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self._dossier = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self.api = creer_api({"donnees": self._dossier.name, "corpus": CORPUS})
        self.api.juge = None
        self.api.fournisseur = FournisseurDouble()
        self.api.fournisseur_juge = FournisseurDouble()

    def tearDown(self):
        fixer_horloge(None)
        os.environ.clear()
        os.environ.update(self._env)
        self._dossier.cleanup()

    def appeler(self, methode, chemin, corps=None):
        return router(methode, chemin, corps or {},
                      {"Authorization": "Bearer " + JETON}, self.api)


class TestInterrupteurCible(BaseModeReel):
    """PIEGE_CIBLE_TYPE bascule toute l'instance sur une cible réelle."""

    def test_defaut_local(self):
        os.environ.pop("PIEGE_CIBLE_TYPE", None)
        from piege.cibles.locale import CibleLocaleDemo

        self.assertIsInstance(self.api.cible("APP-1", {"corpus": CORPUS}),
                              CibleLocaleDemo)

    def test_bascule_inferhub(self):
        os.environ["PIEGE_CIBLE_TYPE"] = "inferhub"
        cible = self.api.cible("APP-2", {"corpus": CORPUS,
                                         "fournisseur": FournisseurDouble()})
        self.assertIsInstance(cible, CibleInferhub)

    def test_spec_explicite_prioritaire(self):
        os.environ["PIEGE_CIBLE_TYPE"] = "inferhub"
        from piege.cibles.locale import CibleLocaleDemo

        cible = self.api.cible("APP-3", {"type": "local", "corpus": CORPUS})
        self.assertIsInstance(cible, CibleLocaleDemo)


class TestPlafondTechniques(BaseModeReel):
    """PIEGE_MAX_TECHNIQUES refuse au lieu de tronquer (instance publique)."""

    def mandat(self, techniques):
        self.appeler("POST", "/applications",
                     {"id": "APP-guichet", "nom": "Guichet", "type": "rag",
                      "environnement": "test", "exposition": 2,
                      "depot_document_autorise": True})
        _, corps = self.appeler("POST", "/mandats", {
            "application_id": "APP-guichet", "perimetre_techniques": techniques,
            "environnements": ["test"], "fenetre_debut": "2026-11-01T00:00:00Z",
            "fenetre_fin": "2027-12-01T00:00:00Z", "budget_appels": 50,
            "budget_jetons": 500000, "contact_urgence": "x"})
        return corps["donnees"]["mandat"]["id"]

    def test_plafond_depasse_refuse(self):
        os.environ["PIEGE_MAX_TECHNIQUES"] = "1"
        mandat_id = self.mandat(["A1", "C1", "F3"])
        statut, corps = self.appeler("POST", "/campagnes",
                                     {"mandat_id": mandat_id, "graine": 7})
        self.assertEqual(statut, 400)
        self.assertEqual(corps["erreur"]["code"], "plafond_techniques")
        self.assertIn("plafond", corps["erreur"]["message"])

    def test_sous_plafond_accepte(self):
        os.environ["PIEGE_MAX_TECHNIQUES"] = "5"
        mandat_id = self.mandat(["A1"])
        statut, corps = self.appeler("POST", "/campagnes",
                                     {"mandat_id": mandat_id, "graine": 7,
                                      "cible_spec": {"corpus": CORPUS}})
        self.assertEqual(statut, 200)
        self.assertEqual(corps["donnees"]["executions"], 1)

    def test_sans_plafond_aucune_limite(self):
        os.environ.pop("PIEGE_MAX_TECHNIQUES", None)
        mandat_id = self.mandat(["A1", "C1"])
        statut, corps = self.appeler("POST", "/campagnes",
                                     {"mandat_id": mandat_id, "graine": 7,
                                      "cible_spec": {"corpus": CORPUS}})
        self.assertEqual(statut, 200)
        self.assertEqual(corps["donnees"]["executions"], 2)

    def test_plafond_invalide(self):
        os.environ["PIEGE_MAX_TECHNIQUES"] = "beaucoup"
        mandat_id = self.mandat(["A1"])
        statut, _ = self.appeler("POST", "/campagnes",
                                 {"mandat_id": mandat_id, "graine": 7,
                                  "cible_spec": {"corpus": CORPUS}})
        self.assertEqual(statut, 400)


if __name__ == "__main__":
    unittest.main()
