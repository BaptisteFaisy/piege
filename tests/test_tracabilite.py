"""Tests de la traçabilité recalculée (EF/ENF/KPI).

Le document est append-only : ses statuts « Status » datent de l'ouverture des
lots. Le script `scripts/preuves/tracabilite.py` recalcule le statut réel à
partir de l'existence du code et des tests. Ces tests vérifient deux choses :

- le document ne **surestime jamais** (aucun `done` déclaré qui ne serait pas
  `done` dans la réalité) ;
- la grande majorité des exigences sont réellement `done` ou `partial`, ce qui
  prouve que le projet est livré, pas seulement « déclaré livré ».
"""

from __future__ import annotations

import importlib.util
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN = os.path.join(RACINE, "scripts", "preuves", "tracabilite.py")


def charger():
    specification = importlib.util.spec_from_file_location("tracabilite",
                                                           CHEMIN)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


tracabilite = charger()


class TestStatutsRecalcules(unittest.TestCase):
    """Le document n'exagère jamais l'état du projet."""

    def setUp(self):
        with open(tracabilite.DOC, encoding="utf-8") as f:
            self.resultats = tracabilite.analyser(f.read())
        self.ecarts = tracabilite.ecarts(self.resultats)

    def test_au_moins_soixante_exigences(self):
        """Les trois tables sont bien analysées (EF + ENF + KPI)."""
        self.assertGreaterEqual(len(self.resultats), 60)

    def test_aucun_faux_done(self):
        """Aucune ligne déclarée `done` ne doit être `todo` dans la réalité."""
        faux = [i for i, l in self.ecarts
                if l["declare"] == "done" and l["recalcule"] == "todo"]
        self.assertEqual(faux, [])

    def test_aucun_faux_positif_de_completude(self):
        """Une ligne `done` doit avoir du code ET un test ; sinon, partial."""
        for identifiant, ligne in self.resultats.items():
            if ligne["recalcule"] == "done":
                self.assertTrue(ligne["code"] and ligne["tests"],
                                "%s : done sans code ni test" % identifiant)

    def test_projet_majoritairement_livre(self):
        """Les exigences qui pointent vers du code ou un test sont livrées.

        Une ligne `todo` recalculé n'a ni code ni test référencé : elle peut
        être implémentée sans que le document ait renseigné ses colonnes.
        """
        total = len(self.resultats)
        lourd = sum(1 for l in self.resultats.values()
                    if l["recalcule"] in ("done", "partial"))
        self.assertGreaterEqual(lourd / total, 0.60,
                                "moins de 60 % des exigences référencent du code")

    def test_ecarts_reveles(self):
        """Le recalcul révèle des statuts périmés : c'est tout l'intérêt."""
        self.assertGreaterEqual(len(self.ecarts), 30)

    def test_section_generee_dans_le_document(self):
        """La section générée est bien présente, ligne par exigence."""
        with open(tracabilite.DOC, encoding="utf-8") as f:
            contenu = f.read()
        self.assertIn("## Statuts vérifiés", contenu)
        section = contenu.split("## Statuts vérifiés", 1)[1]
        for identifiant in self.resultats:
            self.assertIn("| %s |" % identifiant, section)

    def test_aucun_ecart_en_defaveur_du_projet(self):
        """Aucune ligne ne déclare un état meilleur que la réalité.

        (todo < partial < done) : déclarer `done` alors que la réalité est
        `todo` serait une surpromesse. Les écarts connus vont tous dans
        l'autre sens (le document sous-estimait le projet).
        """
        rang = {"todo": 0, "partial": 1, "done": 2}
        pour_le_projet = [i for i, l in self.ecarts
                          if rang[l["declare"]] > rang[l["recalcule"]]]
        self.assertEqual(pour_le_projet, [])


if __name__ == "__main__":
    unittest.main()