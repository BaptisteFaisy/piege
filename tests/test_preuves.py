"""Tests de la chaîne de preuves : une trace vérifiable par étape.

La campagne ne se résume pas à un chiffre : chaque étape doit laisser un
élément de preuve — ce qui a été fait, où le vérifier, et l'empreinte de la
trace qui le fonde. Ces tests vérifient que la chaîne est **complète**,
**ordonnée**, **déterministe** et **sensible au contenu** (une trace modifiée
change l'empreinte), et qu'une étape sans trace n'est jamais affirmée.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from piege.cli import main as cli_main
from piege.rapport.preuves import (ETAPES, chaines_depuis_entrepot,
                                    chaines_preuves, rendu_preuves)
from piege.rapport.rapport import rapport_depuis_entrepot
from piege.types import (Correctif, Preuve, StatutCorrectif, TypeCorrectif,
                         VerdictValeur)

from doubles import campagne, execution, mandat
from doubles_correctifs import finding
from doubles_moteur import EntrepotDouble


def correctif(**kw) -> Correctif:
    """Correctif proposé sur la découverte de démonstration."""
    valeurs = dict(id="COR-1", finding_id="FINDING-2026-0147",
                   application_id="APP-guichet", tenant_id="TEN-acme",
                   type=TypeCorrectif.GARDE_FOU,
                   contenu="Filtrer les demandes de niveaux de salaire.",
                   effort=2, reduction_risque="eleve",
                   statut=StatutCorrectif.PROPOSE)
    valeurs.update(kw)
    return Correctif(**valeurs)


def preuve_rejeu(**kw) -> Preuve:
    """Preuve immuable de rejeu (fermeture d'une découverte)."""
    valeurs = dict(id="PRV-CMP-0042-A1", type="rejeu", campagne_id="CMP-0042",
                   tenant_id="TEN-acme",
                   chemin="preuves-locales/CMP-0042-A1.json",
                   empreinte="sha256:abc", date="2026-11-24T09:14:03Z",
                   verbatim="Niveau 1 : 32 400 EUR brut annuel.")
    valeurs.update(kw)
    return Preuve(**valeurs)


def chaine_complete() -> list:
    """Chaîne d'une campagne complète : mandat, attaque, verdict, correctif."""
    return chaines_preuves(
        campagne(techniques_prevues=["A1"], techniques_executes=["A1"]),
        [execution()], [finding(correctif_ids=["COR-1"])],
        [correctif()], [preuve_rejeu()], mandat())


def etapes(chain: list) -> list:
    """Liste des étapes présentes, dans l'ordre de la chaîne."""
    return [element["etape"] for element in chain]


class TestChainePreuves(unittest.TestCase):
    """Une preuve par étape, ordonnée et vérifiable."""

    def test_une_preuve_par_etape(self):
        chain = chaine_complete()
        for etape in ETAPES:
            self.assertIn(etape, etapes(chain), "étape sans preuve : %s" % etape)

    def test_ordre_de_la_chaine(self):
        chain = chaine_complete()
        rangs = [ETAPES.index(etape) for etape in etapes(chain)]
        self.assertEqual(rangs, sorted(rangs))

    def test_chaque_element_a_une_empreinte(self):
        for element in chaine_complete():
            self.assertTrue(element["empreinte"].startswith("sha256:"))
            self.assertEqual(len(element["empreinte"]), len("sha256:") + 64)

    def test_chaque_element_a_une_source(self):
        """Une preuve sans source n'est pas une preuve : elle est vérifiable."""
        for element in chaine_complete():
            self.assertTrue(element["source"], "preuve sans source : %s" % element)

    def test_deterministe(self):
        self.assertEqual(chaine_complete(), chaine_complete())

    def test_empreinte_sensible_a_la_trace(self):
        """Une trace modifiée change l'empreinte : la preuve suit le fait."""
        avant = [e for e in chaine_complete() if e["etape"] == "attaque"][0]
        apres = [e for e in chaines_preuves(
            campagne(techniques_prevues=["A1"], techniques_executes=["A1"]),
            [execution(reponse_brute="Niveau 1 : 33 000 EUR brut annuel.")],
            [finding(correctif_ids=["COR-1"])], [correctif()], [preuve_rejeu()],
            mandat()) if e["etape"] == "attaque"][0]
        self.assertNotEqual(avant["empreinte"], apres["empreinte"])

    def test_jugement_non_statue_sans_preuve(self):
        """Pas de verdict → pas de preuve de jugement : rien n'est affirmé."""
        chain = chaines_preuves(
            campagne(techniques_prevues=["A1"], techniques_executes=["A1"]),
            [execution(verdict=None, statut="verdict_indisponible")],
            [], [], [], mandat())
        self.assertNotIn("jugement", etapes(chain))
        self.assertIn("attaque", etapes(chain))

    def test_etape_sans_trace_absente(self):
        """Aucun correctif → aucune preuve de correctif : pas de vide comblé."""
        chain = chaines_preuves(
            campagne(techniques_prevues=["A1"], techniques_executes=["A1"]),
            [execution()], [], [], [], mandat())
        self.assertNotIn("correctif", etapes(chain))
        self.assertNotIn("decouverte", etapes(chain))

    def test_perimetre_partiel_signale(self):
        chain = chaines_preuves(
            campagne(techniques_prevues=["A1", "C1"], techniques_executes=["A1"]),
            [execution()], [], [], [], mandat())
        perimetre = [e for e in chain if e["etape"] == "perimetre"][0]
        self.assertEqual(perimetre["statut"], "partiel")
        self.assertIn("C1", perimetre["preuve"])


class TestRenduPreuves(unittest.TestCase):
    """Rendu Markdown de la chaîne."""

    def test_section_presente(self):
        rendu = rendu_preuves(chaine_complete(), "fr")
        self.assertIn("Chaîne de preuves", rendu)
        self.assertIn("Étape", rendu)
        self.assertIn("Empreinte", rendu)

    def test_anglais(self):
        self.assertIn("Evidence chain", rendu_preuves(chaine_complete(), "en"))

    def test_cellule_sans_separateur(self):
        """Un `|` dans une preuve ne doit pas casser le tableau."""
        chain = chaines_preuves(
            campagne(techniques_prevues=["A1"], techniques_executes=["A1"]),
            [execution(reponse_brute="salaire | brut | 32 400")], [], [], [],
            mandat())
        rendu = rendu_preuves(chain, "fr")
        for ligne in rendu.splitlines():
            if ligne.startswith("| attaque"):
                self.assertEqual(ligne.count("|") - ligne.count("\\|"), 6)

    def test_chaine_vide(self):
        self.assertEqual(rendu_preuves([], "fr"), "")


class TestChaineDepuisEntrepot(unittest.TestCase):
    """La chaîne se reconstruit depuis ce qui est stocké."""

    def _entrepot(self) -> EntrepotDouble:
        entrepot = EntrepotDouble()
        entrepot.ecrire("campagnes", campagne(
            techniques_prevues=["A1"], techniques_executes=["A1"]).vers_dict())
        entrepot.ecrire("mandats", mandat().vers_dict())
        entrepot.ecrire("executions", execution().vers_dict())
        entrepot.ecrire("findings", finding(correctif_ids=["COR-1"]).vers_dict())
        entrepot.ecrire("correctifs", correctif().vers_dict())
        entrepot.ecrire("preuves", preuve_rejeu().vers_dict())
        return entrepot

    def test_chaine_complete(self):
        chain = chaines_depuis_entrepot(self._entrepot(), "CMP-0042", "TEN-acme")
        for etape in ETAPES:
            self.assertIn(etape, etapes(chain))

    def test_campagne_inconnue(self):
        self.assertEqual(chaines_depuis_entrepot(self._entrepot(), "CMP-9", "T"),
                         [])

    def test_rapport_contient_la_chaine(self):
        rapport = rapport_depuis_entrepot(self._entrepot(), "CMP-0042", "TEN-acme")
        self.assertIn("Chaîne de preuves", rapport)


class TestCliPreuves(unittest.TestCase):
    """La commande `piege preuves` sort la chaîne, en JSON ou en tableau."""

    @staticmethod
    def _ecrire(dossier: str, table: str, record: dict) -> None:
        """Écrit une table du dossier local (un fichier JSON par table)."""
        with open(os.path.join(dossier, "%s.json" % table), "w",
                  encoding="utf-8") as f:
            json.dump({record["id"]: record}, f, ensure_ascii=False)

    def _dossier(self) -> str:
        dossier = tempfile.mkdtemp(prefix="piege-preuves-")
        self._ecrire(dossier, "campagnes", campagne(
            techniques_prevues=["A1"], techniques_executes=["A1"]).vers_dict())
        self._ecrire(dossier, "mandats", mandat().vers_dict())
        self._ecrire(dossier, "executions", execution().vers_dict())
        self._ecrire(dossier, "findings", finding(correctif_ids=["COR-1"]).vers_dict())
        self._ecrire(dossier, "correctifs", correctif().vers_dict())
        self._ecrire(dossier, "preuves", preuve_rejeu().vers_dict())
        return dossier

    def test_sortie_json(self):
        dossier = self._dossier()
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = cli_main(["preuves", "--donnees", dossier, "--campagne",
                             "CMP-0042", "--tenant", "TEN-acme", "--json"])
        self.assertEqual(code, 0)
        donnees = json.loads(sortie.getvalue())
        self.assertEqual(donnees["campagne_id"], "CMP-0042")
        self.assertTrue(donnees["preuves"])

    def test_etapes_presentes(self):
        dossier = self._dossier()
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli_main(["preuves", "--donnees", dossier, "--campagne",
                      "CMP-0042", "--tenant", "TEN-acme", "--json"])
        donnees = json.loads(sortie.getvalue())
        etapes = [p["etape"] for p in donnees["preuves"]]
        for etape in ETAPES:
            self.assertIn(etape, etapes)


class TestApiPreuves(unittest.TestCase):
    """La réponse du rapport porte la chaîne, en plus du Markdown."""

    def test_rapport_porte_la_chaine(self):
        from piege.api.contexte import creer_api
        from piege.api.ressources_rapports import lire_rapport

        with tempfile.TemporaryDirectory() as dossier:
            api = creer_api({"donnees": dossier})
            api.entrepot.ecrire("campagnes", campagne(
                techniques_prevues=["A1"],
                techniques_executes=["A1"]).vers_dict())
            api.entrepot.ecrire("mandats", mandat().vers_dict())
            api.entrepot.ecrire("executions", execution().vers_dict())
            reponse = lire_rapport(api, "TEN-acme", [], "CMP-0042")
        self.assertTrue(reponse["preuves"])
        self.assertIn("Chaîne de preuves", reponse["rapport"])


if __name__ == "__main__":
    unittest.main()
