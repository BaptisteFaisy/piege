"""Tests de la table de preuve des recettes (R1..R20).

Chaque recette du cahier des charges doit être **prouvée** par un test qui
s'exécute. Ce module vérifie trois choses :
- la liaison existe : chaque recette a au moins une preuve ;
- la liaison est **vivante** : chaque fichier et chaque nœud de test existe
  réellement (une preuve qui pointe dans le vide ne prouve rien) ;
- la preuve **passe** : l'exécution des tests liés rend 20/20 recettes prouvées.

La suite complète du projet dure quelques secondes : ce test peut donc
s'exécuter à chaque CI, et faire échouer la build si une recette cesse d'être
prouvée.
"""

from __future__ import annotations

import importlib.util
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_SCRIPT = os.path.join(RACINE, "scripts", "preuves", "recettes.py")


def charger_script():
    """Charge le script de preuve comme module (scripts/ n'est pas un paquet)."""
    specification = importlib.util.spec_from_file_location("recettes_preuves",
                                                           CHEMIN_SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


recettes = charger_script()


class TestLiaisonRecettes(unittest.TestCase):
    """Chaque recette du cahier est reliée à une preuve exécutable."""

    def setUp(self):
        self.exigences = recettes.lire_recettes()
        self.liaison = recettes.lier(self.exigences)

    def test_cahier_lu(self):
        self.assertEqual(len(self.exigences), 20)

    def test_chaque_recette_a_une_preuve(self):
        for identifiant in sorted(self.exigences, key=lambda r: int(r[1:])):
            self.assertTrue(self.liaison.get(identifiant),
                            "recette sans preuve : %s" % identifiant)

    def test_fichiers_de_preuve_existants(self):
        for preuves in self.liaison.values():
            for preuve in preuves:
                fichier = preuve.split("::")[0]
                self.assertTrue(os.path.isfile(os.path.join(RACINE, fichier)),
                                "preuve vers un fichier absent : %s" % preuve)

    def test_noeuds_de_test_resolvables(self):
        """Un nœud doit exister (classe et méthode) : sinon pytest ne le voit pas."""
        for preuves in self.liaison.values():
            for preuve in preuves:
                if "::" not in preuve:
                    continue
                fichier = os.path.join(RACINE, preuve.split("::")[0])
                with open(fichier, encoding="utf-8") as f:
                    contenu = f.read()
                morceaux = preuve.split("::")
                self.assertIn("class %s" % morceaux[1], contenu,
                              "classe absente : %s" % preuve)
                self.assertIn("def %s" % morceaux[2], contenu,
                              "test absent : %s" % preuve)

    def test_complement_sans_fichier_inexistant(self):
        for identifiant, fichiers in recettes.COMPLEMENT.items():
            for fichier in fichiers:
                self.assertTrue(os.path.isfile(os.path.join(RACINE, fichier)),
                                "complément vers un fichier absent : %s" % fichier)


class TestExecutionDeLaPreuve(unittest.TestCase):
    """La preuve s'exécute : les tests des recettes passent."""

    def test_toutes_les_recettes_sont_prouvees(self):
        exigences = recettes.lire_recettes()
        liaison = recettes.lier(exigences)
        etats = recettes.executer([preuve for preuves in liaison.values()
                                   for preuve in preuves])
        resultats = recettes.resultats(liaison, etats)
        manquant = [identifiant for identifiant, valeur in resultats.items()
                    if valeur["statut"] != "prouve"]
        self.assertEqual(manquant, [],
                         "recettes non prouvées : %s" % ", ".join(manquant))


if __name__ == "__main__":
    unittest.main()
