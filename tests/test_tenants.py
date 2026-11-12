"""Tests de la sortie de client : `DELETE /tenants/{id}` et rétention (ENF-08, R20).

Le runbook annonçait `DELETE /tenants/{id}` sans que la route existe. Elle est
ici, avec la preuve de purge (empreinte + fichier) et la durée de rétention
lue — le champ `Tenant.retention_jours` n'est plus mort.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from piege.api.contexte import creer_api
from piege.api.routeur import router
from piege.securite import retention
from piege.types import fixer_horloge

INSTANT = "2026-11-24T09:14:03Z"
JETON_A = "jeton:TEN-acme:commanditaire:analyste"
JETON_A_COMMANDITAIRE = "jeton:TEN-acme:commanditaire"


def _campagne(tenant_id="TEN-acme", identifiant="CMP-1") -> dict:
    return {"id": identifiant, "tenant_id": tenant_id, "mandat_id": "MAN-1",
            "application_id": "APP-guichet", "type": "complete", "graine": 1,
            "statut": "terminee", "debutee_le": INSTANT}


class BasePuissance(unittest.TestCase):
    """Contexte d'API hors ligne avec des données d'un tenant."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self._dossier = tempfile.TemporaryDirectory()
        self.api = creer_api({"donnees": self._dossier.name})
        self.api.entrepot.ecrire("campagnes", _campagne())
        self.api.entrepot.ecrire("executions",
                                 {"id": "EXE-1", "tenant_id": "TEN-acme",
                                  "campagne_id": "CMP-1", "statut": "execute"})
        self.api.entrepot.ecrire("tenants",
                                 {"id": "TEN-acme", "nom_client": "Acme",
                                  "contact_commanditaire": "rh@acme.fr",
                                  "retention_jours": 60})

    def tearDown(self):
        fixer_horloge(None)
        self._dossier.cleanup()

    def appeler(self, methode, chemin, jeton=JETON_A):
        entetes = {"Authorization": "Bearer %s" % jeton}
        return router(methode, chemin, {}, entetes, self.api)


class TestPurgeDeTenant(BasePuissance):
    """La purge est routée, prouvée et journalisée."""

    def test_purge_par_analyste(self):
        statut, corps = self.appeler("DELETE", "/tenants/TEN-acme")
        self.assertEqual(statut, 200)
        donnees = corps["donnees"]
        self.assertEqual(donnees["tenant_id"], "TEN-acme")
        self.assertEqual(donnees["retention_jours"], 60)
        self.assertTrue(donnees["preuve"]["empreinte"].startswith("sha256:"))
        # les données ont réellement disparu
        self.assertIsNone(self.api.entrepot.lire("campagnes", "CMP-1"))

    def test_preuve_de_purge_ecrite(self):
        self.appeler("DELETE", "/tenants/TEN-acme")
        preuves = self.api.entrepot.lister("preuves", tenant_id="TEN-acme")
        purges = [p for p in preuves if p.get("type") == "purge"]
        self.assertEqual(len(purges), 1)

    def test_journal_trace_la_purge(self):
        self.appeler("DELETE", "/tenants/TEN-acme")
        lignes = self.api.entrepot.lire_journal()
        self.assertTrue(any(l.get("quoi") == "tenant_purge" for l in lignes))

    def test_client_ne_purge_que_son_tenant(self):
        statut, corps = self.appeler("DELETE", "/tenants/TEN-bolt",
                                     jeton=JETON_A_COMMANDITAIRE)
        self.assertEqual(statut, 403)

    def test_analyste_purge_un_autre_tenant(self):
        statut, corps = self.appeler("DELETE", "/tenants/TEN-bolt")
        self.assertEqual(statut, 200)


class TestRetention(BasePuissance):
    """La durée de rétention est lue et opposable."""

    def test_delai_lu_du_tenant(self):
        self.assertEqual(retention.delai_retention(self.api.entrepot, "TEN-acme"),
                         60)

    def test_delai_par_defaut_sans_tenant(self):
        self.assertEqual(retention.delai_retention(self.api.entrepot, "INCONNU"),
                         365)

    def test_expiration_calculee(self):
        limite = retention.expiration(60, "2026-11-24T09:14:03Z")
        self.assertEqual(limite, "2026-09-25T09:14:03Z")

    def test_expiration_bornée(self):
        """Un délai invalide est borné : jamais négatif ni nul."""
        self.api.entrepot.ecrire("tenants",
                                 {"id": "TEN-nul", "retention_jours": 0})
        self.assertEqual(retention.delai_retention(self.api.entrepot, "TEN-nul"),
                         1)


class TestRouteEnregistree(unittest.TestCase):
    """La route est bien dans la table de routes de l'API."""

    def test_route_presente(self):
        from piege.api import routes

        exposees = {(m, c) for m, c, _ in routes()}
        self.assertIn(("DELETE", "/tenants/{id}"), exposees)


if __name__ == "__main__":
    unittest.main()