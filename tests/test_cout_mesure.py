"""Tests du coût mesuré de bout en bout (ENF-10, KPI-7).

Le routeur de modèles renvoie le coût réel de chaque appel. Ce coût doit
remonter dans l'exécution, puis dans la campagne : un rapport qui affiche un
coût estimé alors qu'un coût réel existe est exactement ce que le service
promet de ne pas faire.
"""

from __future__ import annotations

import unittest

from piege.moteur import ConfigurationCampagne, executer_campagne
from piege.types import Reponse, fixer_horloge

from doubles import application, mandat, technique
from doubles_moteur import EntrepotDouble, JournalDouble, juge_double

INSTANT = "2026-11-24T09:14:03Z"
COUT_PAR_APPEL = 0.00002


class CibleFacturee:
    """Cible dont chaque réponse porte un coût réel, comme le routeur InferHub."""

    def __init__(self, cout=COUT_PAR_APPEL):
        self.id = "APP-guichet"
        self.application_id = "APP-guichet"
        self.cout = cout
        self.appels = 0

    def sonder(self, demande, session, graine):
        self.appels += 1
        return Reponse(texte="Voici la grille : Niveau 1 : 32 400 EUR brut annuel.",
                       jetons_entree=900, jetons_sortie=60, latence_ms=1200,
                       brut={"cout": self.cout, "modele_reel": "modele-test"},
                       session=session)

    def mesurer(self, requete, session):
        return self.sonder(requete, session, 0)

    def deposer_document(self, chemin, contenu, session):
        return "doc-1"

    def reindexer(self, session):
        return None

    def detruire_index(self, index_id):
        return None

    def journaliser(self, evenement):
        return None


def config(cible, techniques, **kw) -> ConfigurationCampagne:
    """Configuration de campagne avec une cible qui facture."""
    valeurs = dict(mandat=mandat(perimetre_techniques=[t.id for t in techniques]),
                   application=application(), cible=cible, techniques=techniques,
                   graine=20261124, parallelisme=1, juge=juge_double(),
                   journal=JournalDouble(), entrepot=EntrepotDouble())
    valeurs.update(kw)
    return ConfigurationCampagne(**valeurs)


class TestCoutMesure(unittest.TestCase):
    """Le coût remonte de l'appel de modèle jusqu'à la campagne."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_cout_par_execution(self):
        cible = CibleFacturee()
        executer_campagne(config(cible, [technique(id="A1", tours_max=1)]))
        # Une exécution = un appel de modèle = un coût.
        self.assertEqual(cible.appels, 1)

    def test_cout_de_campagne_non_nul(self):
        cible = CibleFacturee()
        campagne = executer_campagne(config(cible, [technique(id="A1", tours_max=1)]))
        self.assertAlmostEqual(campagne.cout_mesure, COUT_PAR_APPEL, places=8)

    def test_cout_cumule_sur_plusieurs_techniques(self):
        cible = CibleFacturee()
        techniques = [technique(id="A1", tours_max=1), technique(id="C1", tours_max=1)]
        campagne = executer_campagne(config(cible, techniques))
        self.assertEqual(cible.appels, 2)
        self.assertAlmostEqual(campagne.cout_mesure, 2 * COUT_PAR_APPEL, places=8)

    def test_cout_cumule_sur_les_tours(self):
        """Une technique multi-tours facture chaque tour."""
        cible = CibleFacturee()
        campagne = executer_campagne(
            config(cible, [technique(id="A4", tours_max=3, budget_appels=3)]))
        self.assertEqual(cible.appels, 3)
        self.assertAlmostEqual(campagne.cout_mesure, 3 * COUT_PAR_APPEL, places=8)

    def test_cout_nul_sans_facturation(self):
        """Une cible qui ne renvoie pas de coût ne produit pas de coût inventé."""
        cible = CibleFacturee(cout=0.0)
        campagne = executer_campagne(config(cible, [technique(id="A1", tours_max=1)]))
        self.assertEqual(campagne.cout_mesure, 0.0)

    def test_execution_porte_son_cout(self):
        cible = CibleFacturee()
        entrepot = EntrepotDouble()
        executer_campagne(config(cible, [technique(id="A1", tours_max=1)],
                                 entrepot=entrepot))
        executions = entrepot.lister("executions")
        self.assertEqual(len(executions), 1)
        self.assertAlmostEqual(executions[0]["cout"], COUT_PAR_APPEL, places=8)

    def test_arrondi_stable(self):
        """Pas de dérive flottante sur l'arrondi cumulé."""
        cible = CibleFacturee(cout=0.00001)
        techniques = [technique(id="A%d" % i, tours_max=1) for i in range(1, 8)]
        campagne = executer_campagne(
            config(cible, techniques,
                   mandat=mandat(perimetre_techniques=[t.id for t in techniques])))
        self.assertAlmostEqual(campagne.cout_mesure, 7 * 0.00001, places=9)
        # Arrondi à 6 décimales : aucune queue flottante au-delà.
        self.assertEqual(campagne.cout_mesure, round(campagne.cout_mesure, 6))

    def test_cout_expose_dans_le_budget(self):
        """Le budget exposé par l'API reprend le coût mesuré de la campagne."""
        from piege.observabilite import budget_restant

        cible = CibleFacturee()
        campagne = executer_campagne(config(cible, [technique(id="A1", tours_max=1)]))
        etat = budget_restant(campagne, mandat=mandat())
        self.assertAlmostEqual(etat["cout_mesure"], COUT_PAR_APPEL, places=8)


if __name__ == "__main__":
    unittest.main()
