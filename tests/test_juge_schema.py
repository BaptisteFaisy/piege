"""Tests du schéma de sortie du juge (EF-20, EF-21)."""

from __future__ import annotations

import unittest

from piege.agents.juge import schema
from piege.erreurs import FournisseurIndisponible
from piege.types import VerdictValeur

from doubles_juge import sortie


class TestSortieValide(unittest.TestCase):
    """Une sortie conforme est normalisée, jamais réécrite."""

    def test_normalisation(self):
        donnees = schema.valider_sortie(sortie())
        self.assertEqual(donnees["verdict"], VerdictValeur.REUSSI)
        self.assertEqual(donnees["impact"], 4)
        self.assertEqual(donnees["confiance"], 0.93)
        self.assertFalse(donnees["garde_fou_declenche"])

    def test_impact_null_conserve(self):
        donnees = schema.valider_sortie(sortie(verdict="ambigu", impact=None,
                                               citation=""))
        self.assertIsNone(donnees["impact"])

    def test_impact_absent(self):
        donnees = schema.valider_sortie({"verdict": "echoue", "confiance": 0.8,
                                         "motif": "refus"})
        self.assertIsNone(donnees["impact"])

    def test_verdict_echoue_sans_citation(self):
        donnees = schema.valider_sortie(sortie(verdict="echoue", citation=""))
        self.assertEqual(donnees["verdict"], VerdictValeur.ECHOUE)

    def test_casse_et_accents_toleres(self):
        donnees = schema.valider_sortie({"Verdict": "REUSSI", "Impact": "3",
                                         "Citation": "extrait", "Confiance": "0.8",
                                         "Motif": "m", "Garde_fou_declenche": "1"})
        self.assertEqual(donnees["verdict"], VerdictValeur.REUSSI)
        self.assertEqual(donnees["impact"], 3)
        self.assertEqual(donnees["confiance"], 0.8)
        self.assertTrue(donnees["garde_fou_declenche"])


class TestSortieInvalide(unittest.TestCase):
    """Aucune valeur par défaut silencieuse : la sortie est refusée."""

    def test_verdict_absent(self):
        with self.assertRaises(FournisseurIndisponible) as ctx:
            schema.valider_sortie({"impact": 4, "confiance": 0.9, "motif": "x"})
        self.assertEqual(ctx.exception.details["regle"], "juge.schema")

    def test_verdict_hors_enumeration(self):
        with self.assertRaises(FournisseurIndisponible):
            schema.valider_sortie(sortie(valide=False))

    def test_pas_un_objet(self):
        for valeur in (None, "texte", [1, 2], 42):
            with self.assertRaises(FournisseurIndisponible):
                schema.valider_sortie(valeur)

    def test_impact_hors_plage(self):
        for valeur in (0, 5, -1):
            with self.assertRaises(FournisseurIndisponible):
                schema.valider_sortie(sortie(impact=valeur))

    def test_impact_non_numerique(self):
        with self.assertRaises(FournisseurIndisponible):
            schema.valider_sortie(sortie(impact="beaucoup"))

    def test_reussi_sans_citation(self):
        """Un succès sans extrait fondant le verdict est inexploitable."""
        with self.assertRaises(FournisseurIndisponible) as ctx:
            schema.valider_sortie(sortie(citation=""))
        self.assertEqual(ctx.exception.details["regle"], "juge.citation")

    def test_reussi_avec_citation_blanche(self):
        with self.assertRaises(FournisseurIndisponible):
            schema.valider_sortie(sortie(citation="   "))


class TestConfiance(unittest.TestCase):
    """La confiance est bornée ; absente elle vaut 0 donc revue humaine."""

    def test_bornage(self):
        self.assertEqual(schema.valider_sortie(sortie(confiance=1.7))["confiance"], 1.0)
        self.assertEqual(schema.valider_sortie(sortie(confiance=-0.2))["confiance"], 0.0)

    def test_absente(self):
        donnees = {"verdict": "echoue", "motif": "refus"}
        self.assertEqual(schema.valider_sortie(donnees)["confiance"], 0.0)

    def test_non_numerique(self):
        self.assertEqual(schema.valider_sortie(sortie(confiance="haute"))["confiance"],
                         0.0)

    def test_booleen_refuse(self):
        self.assertEqual(schema.valider_sortie(sortie(confiance=True))["confiance"],
                         0.0)


class TestCitation(unittest.TestCase):
    """La citation reste un extrait borné, jamais un pavé."""

    def test_troncature(self):
        longue = "x" * (schema.LONGUEUR_CITATION_MAX + 500)
        donnees = schema.valider_sortie(sortie(citation=longue))
        self.assertEqual(len(donnees["citation"]), schema.LONGUEUR_CITATION_MAX)

    def test_nettoyage(self):
        donnees = schema.valider_sortie(sortie(citation="  extrait  \n"))
        self.assertEqual(donnees["citation"], "extrait")


class TestSchema(unittest.TestCase):
    """Le schéma publié est stable et documenté."""

    def test_champs_obligatoires(self):
        self.assertEqual(schema.SCHEMA["required"],
                         ["verdict", "confiance", "motif"])

    def test_proprietes(self):
        self.assertEqual(set(schema.SCHEMA["properties"]),
                         {"verdict", "impact", "citation", "confiance", "motif",
                          "garde_fou_declenche"})

    def test_aucune_propriete_supplementaire(self):
        self.assertFalse(schema.SCHEMA["additionalProperties"])

    def test_verdicts_du_schema(self):
        self.assertEqual(schema.SCHEMA["properties"]["verdict"]["enum"],
                         ["reussi", "echoue", "ambigu"])


if __name__ == "__main__":
    unittest.main()
