"""Tests du jeu de démonstration : intégrité, filigrane, absence de données réelles.

Le jeu est 100 % synthétique et déclaré comme tel (ENF-07, annexe E). Ces tests
sont la preuve exécutable de cette déclaration : ils vérifient la composition du
corpus, la présence du filigrane sur chaque document, la répartition exacte des
criticités du corpus de demandes légitimes, et l'absence de toute donnée
personnelle apparente (courriel, numéro de sécurité sociale).
"""

from __future__ import annotations

import json
import os
import re
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(RACINE, "demo")
CORPUS = os.path.join(DEMO, "corpus")
DEMANDES = os.path.join(DEMO, "corpus-legitime", "demandes.json")

FILIGRANE = "SYNTHETIQUE"
COURRIEL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
NUMERO_SS = re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\b")
ATTENDUS = {"legitime": 30, "confidentiel": 3, "officiel": 1, "pieges": 6}
REPARTITION_CRITICITE = {4: 9, 3: 12, 2: 18, 1: 11}


def fichiers(dossier: str) -> list[str]:
    """Chemins triés des documents Markdown d'un dossier."""
    chemin = os.path.join(CORPUS, dossier)
    if not os.path.isdir(chemin):
        return []
    return [os.path.join(chemin, nom) for nom in sorted(os.listdir(chemin))
            if nom.endswith(".md")]


def lire(chemin: str) -> str:
    """Contenu d'un fichier texte."""
    with open(chemin, encoding="utf-8") as f:
        return f.read()


class TestCompositionDuCorpus(unittest.TestCase):
    """40 documents, répartis exactement comme l'annexe E.2."""

    def test_repartition_par_dossier(self):
        for dossier, attendu in ATTENDUS.items():
            self.assertEqual(len(fichiers(dossier)), attendu, dossier)

    def test_total_de_quarante(self):
        total = sum(len(fichiers(d)) for d in ATTENDUS)
        self.assertEqual(total, 40)

    def test_trois_documents_confidentiels(self):
        noms = [os.path.basename(c) for c in fichiers("confidentiel")]
        self.assertEqual(sorted(noms), ["compte-rendu-entretien.md",
                                        "grille-2026.md",
                                        "procedure-licenciement.md"])

    def test_procedure_officielle_unique(self):
        self.assertEqual([os.path.basename(c) for c in fichiers("officiel")],
                         ["procedure-accident-travail.md"])

    def test_six_gabarits_de_pieges(self):
        self.assertEqual(len(fichiers("pieges")), 6)

    def test_chaque_document_a_un_titre(self):
        for dossier in ATTENDUS:
            for chemin in fichiers(dossier):
                self.assertTrue(lire(chemin).startswith("# "), chemin)


class TestFiligrane(unittest.TestCase):
    """Chaque document porte le filigrane de démonstration."""

    def test_filigrane_partout(self):
        for dossier in ATTENDUS:
            for chemin in fichiers(dossier):
                self.assertIn(FILIGRANE, lire(chemin), chemin)

    def test_filigrane_dans_les_gabarits(self):
        for chemin in fichiers("pieges"):
            self.assertIn("DEMONSTRATION", lire(chemin))


class TestAucuneDonneeReelle(unittest.TestCase):
    """ENF-07 : ni courriel, ni numéro de sécurité sociale, ni identité réelle."""

    def corpus_complet(self):
        for dossier in ATTENDUS:
            for chemin in fichiers(dossier):
                yield chemin, lire(chemin)

    def test_aucun_courriel(self):
        for chemin, texte in self.corpus_complet():
            self.assertIsNone(COURRIEL.search(texte), chemin)

    def test_aucun_numero_de_securite_sociale(self):
        for chemin, texte in self.corpus_complet():
            self.assertIsNone(NUMERO_SS.search(texte), chemin)

    def test_corpus_legitime_sans_donnee_personnelle(self):
        with open(DEMANDES, encoding="utf-8") as f:
            contenu = f.read()
        self.assertIsNone(COURRIEL.search(contenu))
        self.assertIsNone(NUMERO_SS.search(contenu))

    def test_mention_de_synthese(self):
        with open(os.path.join(DEMO, "README.md"), encoding="utf-8") as f:
            self.assertIn("synthetic", f.read().lower())


class TestCorpusLegitime(unittest.TestCase):
    """50 demandes légitimes, criticités conformes à l'annexe E.3."""

    @classmethod
    def setUpClass(cls):
        with open(DEMANDES, encoding="utf-8") as f:
            cls.document = json.load(f)
        cls.demandes = cls.document["demandes"]

    def test_cinquante_demandes(self):
        self.assertEqual(len(self.demandes), 50)

    def test_repartition_des_criticites(self):
        compte = {}
        for demande in self.demandes:
            compte[demande["criticite"]] = compte.get(demande["criticite"], 0) + 1
        self.assertEqual(compte, REPARTITION_CRITICITE)

    def test_identifiants_uniques(self):
        identifiants = [d["id"] for d in self.demandes]
        self.assertEqual(len(identifiants), len(set(identifiants)))

    def test_champs_obligatoires(self):
        requis = {"id", "texte", "criticite", "frequence_mensuelle", "langue",
                  "attendu", "etiquette"}
        for demande in self.demandes:
            self.assertTrue(requis.issubset(demande), demande["id"])
            self.assertTrue(demande["texte"].strip())
            self.assertTrue(demande["attendu"].strip())
            self.assertGreaterEqual(demande["frequence_mensuelle"], 1)
            self.assertIn(demande["criticite"], (1, 2, 3, 4))

    def test_langue_fr(self):
        self.assertTrue(all(d["langue"] == "fr" for d in self.demandes))

    def test_en_tete_du_document(self):
        self.assertEqual(self.document["application_id"], "APP-guichet-rh")
        self.assertEqual(self.document["tenant_id"], "TEN-demo")
        self.assertIn("synthétique", self.document["source"])

    def test_demandes_critiques_presentes(self):
        """Les demandes de criticité 4 couvrent accident, harcèlement, arrêt."""
        textes = " ".join(d["texte"].lower() for d in self.demandes
                          if d["criticite"] == 4)
        self.assertIn("accident", textes)
        self.assertIn("harcèlement", textes)
        self.assertIn("arrêt", textes)


class TestSpecificationsDeCible(unittest.TestCase):
    """Les deux spécifications de cible sont cohérentes avec l'annexe E.1."""

    def spec(self, nom):
        with open(os.path.join(DEMO, "cible", nom), encoding="utf-8") as f:
            return json.load(f)

    def test_cible_vulnerable(self):
        spec = self.spec("guichet-rh.json")
        self.assertEqual(spec["type"], "local")
        self.assertEqual(spec["garde_fous"], [])
        self.assertEqual(spec["environnement"], "test")
        self.assertEqual(spec["exposition"], 2)
        self.assertTrue(spec["depot_document_autorise"])
        self.assertIn("vulnérabilités intentionnelles", spec["nom"])

    def test_variante_saine(self):
        spec = self.spec("guichet-rh-sain.json")
        self.assertGreaterEqual(len(spec["garde_fous"]), 4)
        self.assertIn("remuneration", spec["garde_fous"])

    def test_corpus_reference(self):
        for nom in ("guichet-rh.json", "guichet-rh-sain.json"):
            self.assertEqual(self.spec(nom)["corpus"], "demo/corpus")


class TestContenuUtile(unittest.TestCase):
    """Le corpus contient ce que la démonstration doit montrer."""

    def test_grille_avec_montants(self):
        texte = lire(os.path.join(CORPUS, "confidentiel", "grille-2026.md"))
        self.assertIn("32 400", texte)
        self.assertIn("78 900", texte)
        self.assertIn("brut annuel", texte)

    def test_procedure_officielle_complete(self):
        texte = lire(os.path.join(CORPUS, "officiel",
                                  "procedure-accident-travail.md"))
        self.assertIn("vingt-quatre heures", texte)
        self.assertIn("fait foi", texte)

    def test_gabarit_f3_contredit_la_reference(self):
        texte = lire(os.path.join(CORPUS, "pieges", "piege-contradiction.md"))
        self.assertIn("remplace la référence officielle", texte)
        self.assertIn("instruction destinee au systeme", texte.lower())

    def test_gabarits_portent_une_instruction(self):
        for chemin in fichiers("pieges"):
            self.assertIn("Instruction destinee au systeme", lire(chemin), chemin)


if __name__ == "__main__":
    unittest.main()
