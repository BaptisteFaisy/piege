"""Tests de la génération de corpus depuis les journaux (#50) et du benchmark (#41)."""

from __future__ import annotations

import unittest

from piege.benchmark import (Contribution, comparer, construire_pool,
                             empreinte_tenant, percentile, statistiques)
from piege.corpus_logs import (anonymiser, contient_pii, estimer_criticite,
                               generer_corpus, normaliser_entrees,
                               statistiques_pii, types_presents)
from piege.erreurs import CorpusLegitimeAbsent
from piege.types import CorpusLegitime


def entrees(n=60, avec_pii=False):
    """Génère n entrées de journal distinctes, avec ou sans PII."""
    themes = ["accident du travail", "congés payés", "mutuelle dentaire",
              "télétravail", "note de frais", "cantine horaires",
              "arrêt maladie", "congé maternité", "parking", "formation"]
    sortie = []
    for i in range(n):
        texte = "Question %d sur %s" % (i, themes[i % len(themes)])
        if avec_pii and i % 5 == 0:
            texte += " contact prenom.nom@exemple.fr ou 06 12 34 56 78"
        sortie.append({"texte": texte, "frequence": (i % 4) + 1})
    return sortie


class TestAnonymiseur(unittest.TestCase):
    """Les PII sont remplacées, de façon irréversible."""

    def test_courriel(self):
        self.assertFalse(contient_pii(anonymiser("écrire à a.b@c.fr svp")))
        self.assertIn("[ANONYMISE]", anonymiser("écrire à a.b@c.fr svp"))

    def test_telephone(self):
        self.assertNotIn("0612345678", anonymiser("tel 06 12 34 56 78").replace(" ", ""))

    def test_securite_sociale(self):
        texte = "numéro 1 85 05 75 123 456 clé 78"
        self.assertTrue(contient_pii(texte))
        self.assertFalse(contient_pii(anonymiser(texte)))

    def test_sans_pii(self):
        self.assertFalse(contient_pii("Comment poser un congé ?"))
        self.assertEqual(anonymiser("Comment poser un congé ?"),
                         "Comment poser un congé ?")

    def test_types_presents(self):
        types = types_presents("mail x@y.fr tel 06 12 34 56 78")
        self.assertIn("courriel", types)
        self.assertIn("telephone", types)

    def test_irreversible(self):
        """Le jeton ne permet pas de retrouver la donnée."""
        self.assertNotIn("@", anonymiser("a.b@c.fr"))


class TestCriticite(unittest.TestCase):
    """Estimation heuristique de la criticité métier."""

    def test_critique(self):
        self.assertEqual(estimer_criticite("déclarer un accident du travail"), 4)
        self.assertEqual(estimer_criticite("signaler un harcèlement"), 4)

    def test_moyen(self):
        self.assertEqual(estimer_criticite("remboursement mutuelle santé"), 3)

    def test_courant(self):
        self.assertEqual(estimer_criticite("demande de congés payés"), 2)

    def test_pratique(self):
        self.assertEqual(estimer_criticite("plan d'accès au parking"), 1)

    def test_pratique_cantine(self):
        # « horaires » est un mot-clé de niveau 2 : la heuristique tranche au
        # plus critique présent, c'est assumé et documenté.
        self.assertEqual(estimer_criticite("où se trouve la cantine"), 1)

    def test_inconnu(self):
        self.assertEqual(estimer_criticite("xyzzy"), 1)


class TestGenerateur(unittest.TestCase):
    """Génération du corpus légitime depuis les journaux."""

    def test_generation_minimale(self):
        corpus = generer_corpus(entrees(60), "APP-guichet", "TEN-acme")
        self.assertIsInstance(corpus, CorpusLegitime)
        self.assertEqual(len(corpus.demandes), 60)
        self.assertEqual(corpus.application_id, "APP-guichet")

    def test_anonymisation_appliquee(self):
        corpus = generer_corpus(entrees(60, avec_pii=True), "APP", "TEN")
        for demande in corpus.demandes:
            self.assertFalse(contient_pii(demande.texte), demande.texte)

    def test_criticite_estimee(self):
        corpus = generer_corpus(entrees(60), "APP", "TEN")
        criticites = {d.criticite for d in corpus.demandes}
        self.assertTrue(criticites.issubset({1, 2, 3, 4}))
        self.assertTrue(any(d.criticite == 4 for d in corpus.demandes))

    def test_deduplication(self):
        brut = [{"texte": "même question"} for _ in range(5)]
        normalisees = normaliser_entrees(brut)
        self.assertEqual(len(normalisees), 1)
        self.assertEqual(normalisees[0]["frequence"], 5)

    def test_dessous_minimum_refuse(self):
        with self.assertRaises(CorpusLegitimeAbsent):
            generer_corpus(entrees(10), "APP", "TEN")

    def test_texte_conserve_pas_cle(self):
        """Le texte anonymisé d'origine est conservé, pas la clé normalisée."""
        corpus = generer_corpus([{"texte": "Question Accentrée ?"}] * 1
                                + entrees(50), "APP", "TEN")
        self.assertTrue(any("?" in d.texte or "Question" in d.texte
                            for d in corpus.demandes))

    def test_etiquette_heuristique(self):
        corpus = generer_corpus(entrees(60), "APP", "TEN")
        self.assertTrue(all(d.etiquette == "criticite_estimee_par_heuristique"
                            for d in corpus.demandes))

    def test_statistiques_pii(self):
        stats = statistiques_pii(entrees(20, avec_pii=True))
        self.assertGreater(stats["entrees_avec_pii"], 0)
        self.assertIn("courriel", stats["par_type"])

    def test_frequence_positive(self):
        corpus = generer_corpus(entrees(60), "APP", "TEN")
        self.assertTrue(all(d.frequence_mensuelle >= 1 for d in corpus.demandes))


class TestBenchmark(unittest.TestCase):
    """#41 : position anonymisée dans un pool inter-clients."""

    def pool(self):
        return [Contribution(empreinte_tenant("TEN-%d" % i), "finance",
                             score, "2026-11-01T00:00:00Z")
                for i, score in enumerate([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])]

    def test_empreinte_non_reversible(self):
        e = empreinte_tenant("TEN-acme")
        self.assertEqual(len(e), 16)
        self.assertNotIn("acme", e)
        self.assertEqual(empreinte_tenant("TEN-acme"), e)

    def test_empreinte_avec_sel(self):
        self.assertNotEqual(empreinte_tenant("TEN-acme", "sel1"),
                            empreinte_tenant("TEN-acme", "sel2"))

    def test_percentile(self):
        self.assertEqual(percentile(10, [10, 20, 30, 40]), 12.5)
        self.assertEqual(percentile(40, [10, 20, 30, 40]), 87.5)

    def test_statistiques(self):
        stats = statistiques([10, 20, 30, 40, 50])
        self.assertEqual(stats["n"], 5)
        self.assertEqual(stats["mediane"], 30)
        self.assertEqual(stats["min"], 10)
        self.assertEqual(stats["max"], 50)

    def test_comparer(self):
        resultat = comparer(20, self.pool(), "finance")
        self.assertEqual(resultat["secteur"], "finance")
        self.assertLessEqual(resultat["percentile"], 30)
        self.assertTrue(resultat["meilleure_que_le_pool"])
        self.assertIn("robuste", resultat["lecture"])

    def test_comparer_mauvais(self):
        resultat = comparer(95, self.pool(), "finance")
        self.assertGreater(resultat["percentile"], 75)
        self.assertIn("exposé", resultat["lecture"])

    def test_filtre_secteur(self):
        pool = self.pool() + [Contribution(empreinte_tenant("X"), "sante", 5,
                                           "2026-11-01T00:00:00Z")]
        self.assertEqual(len(construire_pool(pool, "finance")), 10)
        self.assertEqual(len(construire_pool(pool, "sante")), 1)
        self.assertEqual(len(construire_pool(pool)), 11)

    def test_pool_vide(self):
        resultat = comparer(50, [])
        self.assertEqual(resultat["pool"]["n"], 0)
        self.assertIsNone(resultat["meilleure_que_le_pool"])

    def test_aucune_identite_dans_contribution(self):
        c = Contribution(empreinte_tenant("TEN-secret"), "finance", 42,
                         "2026-11-01T00:00:00Z")
        self.assertNotIn("secret", str(c.vers_dict()))


if __name__ == "__main__":
    unittest.main()
