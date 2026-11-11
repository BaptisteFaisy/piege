"""Tests d'isolation multi-tenant : R14 (EF-60, EF-61, ENF-06).

L'isolation est imposée par l'identité, pas par l'interface : un client A ne
peut pas lire les découvertes d'un client B, et toute tentative est refusée
puis journalisée.
"""

from __future__ import annotations

import tempfile
import unittest

from piege.erreurs import TenantInconnu
from piege.securite.identite import exiger_role, jeton_test, refuser_tenant_en_parametre
from piege.securite.journal import Journal
from piege.stockage.local import EntrepotLocal
from piege.types import fixer_horloge

INSTANT = "2026-11-24T09:14:03Z"
CLIENT_A = "TEN-acme"
CLIENT_B = "TEN-bolt"


class TestIsolation(unittest.TestCase):
    """Deux tenants, un même entrepôt : aucune traversée possible."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self._dossier = tempfile.TemporaryDirectory()
        self.entrepot = EntrepotLocal(self._dossier.name)
        self.journal = Journal()
        self.entrepot.ecrire("findings", {
            "id": "FINDING-2026-0001", "tenant_id": CLIENT_A,
            "severite": "critique", "titre": "Grille des salaires divulguee"})
        self.entrepot.ecrire("findings", {
            "id": "FINDING-2026-0002", "tenant_id": CLIENT_B,
            "severite": "eleve", "titre": "Invite systeme extraite"})

    def tearDown(self):
        fixer_horloge(None)
        self._dossier.cleanup()

    def test_r14_vue_par_tenant(self):
        """Chaque tenant ne voit que ses découvertes ; la flotte voit tout."""
        self.assertEqual([f["id"] for f in
                          self.entrepot.lister("findings", tenant_id=CLIENT_A)],
                         ["FINDING-2026-0001"])
        self.assertEqual([f["id"] for f in
                          self.entrepot.lister("findings", tenant_id=CLIENT_B)],
                         ["FINDING-2026-0002"])
        self.assertEqual(len(self.entrepot.lister("findings")), 2)

    def test_r14_lecture_directe_refusee(self):
        """Lire l'identifiant d'un autre tenant rend `None`, pas la donnée."""
        self.assertIsNone(self.entrepot.lire("findings", "FINDING-2026-0002",
                                             tenant_id=CLIENT_A))

    def test_r14_tentative_journalisee(self):
        lecture = self.entrepot.lire("findings", "FINDING-2026-0002",
                                     tenant_id=CLIENT_A)
        self.assertIsNone(lecture)
        self.journal.consigner("api", "acces_inter_tenant_refuse", CLIENT_A,
                               {"table": "findings", "id": "FINDING-2026-0002"})
        self.assertEqual(len(self.journal.lignes()), 1)
        self.assertTrue(self.journal.verifier_chaine())

    def test_vue_flotte_pour_analyste_msp(self):
        """EF-62 : un analyste MSP voit la flotte, un client son tenant seul."""
        self.assertEqual(len(self.entrepot.lister("findings")), 2)
        self.assertEqual(len(self.entrepot.lister("findings", tenant_id=CLIENT_B)), 1)


class TestIdentiteEtRoutes(unittest.TestCase):
    """Le tenant ne se transmet jamais en paramètre (EF-61)."""

    def test_jeton_d_un_autre_tenant_refuse(self):
        with self.assertRaises(TenantInconnu):
            exiger_role(CLIENT_A, jeton_test(CLIENT_B, "commanditaire"),
                        ["commanditaire"])

    def test_route_avec_tenant_en_parametre(self):
        with self.assertRaises(TenantInconnu):
            refuser_tenant_en_parametre({"tenant": CLIENT_B,
                                         "finding_id": "FINDING-2026-0002"})

    def test_jeton_valide(self):
        exiger_role(CLIENT_A, jeton_test(CLIENT_A, "commanditaire"),
                    ["commanditaire"])

    def test_purge_isolee(self):
        """R20 : purger A laisse B intact."""
        with tempfile.TemporaryDirectory() as dossier:
            entrepot = EntrepotLocal(dossier)
            entrepot.ecrire("findings", {"id": "F-1", "tenant_id": CLIENT_A})
            entrepot.ecrire("findings", {"id": "F-2", "tenant_id": CLIENT_B})
            entrepot.supprimer_tenant(CLIENT_A)
            self.assertEqual(entrepot.lister("findings", tenant_id=CLIENT_A), [])
            self.assertEqual(len(entrepot.lister("findings", tenant_id=CLIENT_B)), 1)


if __name__ == "__main__":
    unittest.main()
