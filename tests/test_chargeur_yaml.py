"""Tests du chargeur YAML : le sous-ensemble strict, sans dépendance tierce."""

from __future__ import annotations

import os
import tempfile
import unittest

from piege.catalogue.chargeur import (ErreurYaml, charger_fichier,
                                      charger_texte)

try:                                                     # pragma: no cover
    import yaml                                          # noqa: F401

    PYYAML = True
except ImportError:                                      # pragma: no cover
    PYYAML = False


class TestCartes(unittest.TestCase):
    """Cartes simples, imbriquées, clés dupliquées refusées."""

    def test_carte_simple(self):
        self.assertEqual(charger_texte("a: 1\nb: deux\n"), {"a": 1, "b": "deux"})

    def test_carte_imbriquee(self):
        texte = "juge:\n  reussi_si: la reponse fuit\n  strict: true\n"
        self.assertEqual(charger_texte(texte),
                         {"juge": {"reussi_si": "la reponse fuit",
                                   "strict": True}})

    def test_cle_dupliquee_refusee(self):
        with self.assertRaises(ErreurYaml) as ctx:
            charger_texte("a: 1\na: 2\n")
        self.assertIn("dupliquée", str(ctx.exception))

    def test_ligne_sans_deux_points(self):
        with self.assertRaises(ErreurYaml):
            charger_texte("juste du texte\n")

    def test_commentaires_ignores(self):
        texte = "# commentaire\na: 1  # commentaire final\n"
        self.assertEqual(charger_texte(texte), {"a": 1})

    def test_diese_quote_conserve(self):
        self.assertEqual(charger_texte('a: "valeur # pas un commentaire"\n'),
                         {"a": "valeur # pas un commentaire"})

    def test_tabulation_refusee(self):
        with self.assertRaises(ErreurYaml):
            charger_texte("a:\n\tb: 1\n")


class TestScalaire(unittest.TestCase):
    """Types scalaires : entiers, flottants, booléens, nuls, quotés."""

    def test_nombres(self):
        self.assertEqual(charger_texte("a: 12\nb: -3\nc: 1.5\nd: 2e3\n"),
                         {"a": 12, "b": -3, "c": 1.5, "d": 2000.0})

    def test_booleens(self):
        self.assertEqual(charger_texte("a: true\nb: false\n"),
                         {"a": True, "b": False})

    def test_oui_reste_une_chaine(self):
        """`oui` est une valeur d'énumération du catalogue, pas un booléen."""
        self.assertEqual(charger_texte("production: oui\n"), {"production": "oui"})
        self.assertEqual(charger_texte("a: non\nb: yes\nc: on\n"),
                         {"a": "non", "b": "yes", "c": "on"})

    def test_nuls(self):
        self.assertEqual(charger_texte("a: null\nb: ~\nc:\n"),
                         {"a": None, "b": None, "c": None})

    def test_quotes(self):
        self.assertEqual(charger_texte('a: "texte"\nb: \'autre\'\n'),
                         {"a": "texte", "b": "autre"})

    def test_echappements(self):
        self.assertEqual(charger_texte('a: "ligne1\\nligne2"\n'),
                         {"a": "ligne1\nligne2"})

    def test_deux_points_dans_valeur_quotee(self):
        self.assertEqual(charger_texte('a: "heure: 10h"\n'), {"a": "heure: 10h"})

    def test_chaine_avec_deux_points_non_quote(self):
        self.assertEqual(charger_texte("a: http://exemple.test/x\n"),
                         {"a": "http://exemple.test/x"})


class TestListes(unittest.TestCase):
    """Listes en bloc et en ligne, avec cartes imbriquées."""

    def test_liste_en_ligne(self):
        self.assertEqual(charger_texte("a: [test, preprod]\n"),
                         {"a": ["test", "preprod"]})

    def test_liste_en_ligne_vide(self):
        self.assertEqual(charger_texte("a: []\n"), {"a": []})

    def test_liste_en_ligne_quotee(self):
        self.assertEqual(charger_texte('a: ["x, y", z]\n'), {"a": ["x, y", "z"]})

    def test_liste_en_bloc(self):
        self.assertEqual(charger_texte("a:\n  - un\n  - deux\n"),
                         {"a": ["un", "deux"]})

    def test_liste_de_cartes(self):
        texte = ("variantes:\n"
                 "  - nom: courte\n"
                 "    sonde: texte court\n"
                 "  - nom: longue\n"
                 "    sonde: texte long\n")
        self.assertEqual(charger_texte(texte),
                         {"variantes": [{"nom": "courte", "sonde": "texte court"},
                                        {"nom": "longue", "sonde": "texte long"}]})

    def test_liste_apres_cle(self):
        texte = "id: A1\nenvironnement: [test]\njuge:\n  reussi_si: x\n"
        self.assertEqual(charger_texte(texte),
                         {"id": "A1", "environnement": ["test"],
                          "juge": {"reussi_si": "x"}})

    def test_ancres_refusees(self):
        with self.assertRaises(ErreurYaml):
            charger_texte("a: &ancre 1\n")
        with self.assertRaises(ErreurYaml):
            charger_texte("a: *autre\n")

    def test_cartes_en_flux_refusees(self):
        with self.assertRaises(ErreurYaml):
            charger_texte("a: {b: 1}\n")


class TestBlocsDeTexte(unittest.TestCase):
    """Blocs repliés et littéraux."""

    def test_replie(self):
        texte = "objectif: >\n  premiere ligne\n  seconde ligne\n"
        self.assertEqual(charger_texte(texte),
                         {"objectif": "premiere ligne seconde ligne\n"})

    def test_litteral(self):
        texte = "objectif: |\n  ligne1\n  ligne2\n"
        self.assertEqual(charger_texte(texte), {"objectif": "ligne1\nligne2\n"})

    def test_bloc_puis_autre_cle(self):
        texte = "objectif: >\n  texte long\nnom: court\n"
        self.assertEqual(charger_texte(texte),
                         {"objectif": "texte long\n", "nom": "court"})

    def test_bloc_vide(self):
        self.assertEqual(charger_texte("objectif: >\n"), {"objectif": ""})


class TestFichier(unittest.TestCase):
    """Chargement depuis un fichier, document vide, fichier absent."""

    def test_fichier(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "t.yaml")
            with open(chemin, "w", encoding="utf-8") as f:
                f.write("a: 1\n")
            self.assertEqual(charger_fichier(chemin), {"a": 1})

    def test_fichier_absent(self):
        with self.assertRaises(OSError):
            charger_fichier("/chemin/inexistant-piege.yaml")

    def test_document_vide(self):
        self.assertIsNone(charger_texte("# seulement un commentaire\n"))


@unittest.skipUnless(PYYAML, "PyYAML absent")
class TestConfrontationPyYaml(unittest.TestCase):
    """Vérification croisée avec PyYAML quand il est installé."""

    def test_meme_resultat(self):
        texte = ("techniques:\n"
                 "  - id: A1\n"
                 "    environnement: [test, preprod]\n"
                 "    budget_appels: 2\n"
                 "    objectif: >\n"
                 "      texte replié\n"
                 "    juge:\n"
                 "      reussi_si: la reponse fuit\n")
        self.assertEqual(charger_texte(texte), yaml.safe_load(texte))
