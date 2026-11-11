"""Tests de l'entrepôt local : écriture atomique, preuves, purge (R20)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from piege.erreurs import ErreurPiege
from piege.stockage.local import EntrepotLocal
from piege.types import fixer_horloge

INSTANT = "2026-11-24T09:14:03Z"


class BaseEntrepot(unittest.TestCase):
    """Dossier temporaire + horloge figée pour chaque test."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self._dossier = tempfile.TemporaryDirectory()
        self.entrepot = EntrepotLocal(self._dossier.name)

    def tearDown(self):
        fixer_horloge(None)
        self._dossier.cleanup()


class TestEcritureLecture(BaseEntrepot):
    """Écriture, lecture, listage filtré par tenant."""

    def finding(self, identifiant, tenant="TEN-acme", severite="critique"):
        return {"id": identifiant, "tenant_id": tenant, "severite": severite,
                "application_id": "APP-guichet", "statut": "ouvert"}

    def test_ecrire_lire(self):
        self.entrepot.ecrire("findings", self.finding("FINDING-2026-0001"))
        lu = self.entrepot.lire("findings", "FINDING-2026-0001")
        self.assertEqual(lu["severite"], "critique")
        self.assertEqual(lu["ecrit_le"], INSTANT)

    def test_lire_absent(self):
        self.assertIsNone(self.entrepot.lire("findings", "FINDING-2026-9999"))

    def test_lister_filtre_par_tenant(self):
        self.entrepot.ecrire("findings", self.finding("FINDING-2026-0001"))
        self.entrepot.ecrire("findings", self.finding("FINDING-2026-0002",
                                                      tenant="TEN-autre"))
        liste = self.entrepot.lister("findings", tenant_id="TEN-acme")
        self.assertEqual([f["id"] for f in liste], ["FINDING-2026-0001"])

    def test_lister_filtre_par_champ(self):
        self.entrepot.ecrire("findings", self.finding("FINDING-2026-0001"))
        self.entrepot.ecrire("findings", self.finding("FINDING-2026-0002",
                                                      severite="faible"))
        liste = self.entrepot.lister("findings", tenant_id="TEN-acme",
                                     severite="faible")
        self.assertEqual([f["id"] for f in liste], ["FINDING-2026-0002"])

    def test_identifiant_alloue(self):
        identifiant = self.entrepot.ecrire("preuves", {"type": "transcription",
                                                       "tenant_id": "TEN-acme"})
        self.assertTrue(identifiant.startswith("PRV-"), identifiant)

    def test_sequences_independantes(self):
        premier = self.entrepot.ecrire("preuves", {"type": "a", "tenant_id": "T"})
        second = self.entrepot.ecrire("preuves", {"type": "b", "tenant_id": "T"})
        self.assertNotEqual(premier, second)

    def test_table_inconnue(self):
        with self.assertRaises(ErreurPiege):
            self.entrepot.ecrire("inconnue", {"id": "X"})

    def test_fichier_atomique_sans_residu(self):
        self.entrepot.ecrire("findings", self.finding("FINDING-2026-0001"))
        residus = [f for f in os.listdir(self._dossier.name) if f.endswith(".tmp")]
        self.assertEqual(residus, [])
        with open(os.path.join(self._dossier.name, "findings.json"),
                  encoding="utf-8") as f:
            self.assertIn("FINDING-2026-0001", json.load(f))


class TestPreuves(BaseEntrepot):
    """Une preuve est immuable : elle se remplace par une nouvelle datée."""

    def test_ecrasement_refuse(self):
        self.entrepot.ecrire("preuves", {"id": "PRV-1", "type": "transcription",
                                         "tenant_id": "TEN-acme"})
        with self.assertRaises(ErreurPiege) as ctx:
            self.entrepot.ecrire("preuves", {"id": "PRV-1", "type": "autre",
                                             "tenant_id": "TEN-acme"})
        self.assertEqual(ctx.exception.code, "preuve_immuable")

    def test_nouvelle_preuve_datee(self):
        self.entrepot.ecrire("preuves", {"id": "PRV-1", "type": "transcription",
                                         "tenant_id": "TEN-acme"})
        second = self.entrepot.ecrire("preuves", {"id": "PRV-2",
                                                  "type": "transcription",
                                                  "tenant_id": "TEN-acme"})
        self.assertEqual(second, "PRV-2")
        self.assertEqual(len(self.entrepot.lister("preuves", "TEN-acme")), 2)


class TestJournal(BaseEntrepot):
    """Journal append-only stocké côté entrepôt."""

    def test_ecriture_et_lecture(self):
        self.entrepot.ecrire_journal({"qui": "moteur", "quoi": "sonde",
                                      "tenant": "TEN-acme"})
        self.entrepot.ecrire_journal({"qui": "moteur", "quoi": "refus",
                                      "tenant": "TEN-acme"})
        lignes = self.entrepot.lire_journal()
        self.assertEqual([l["quoi"] for l in lignes], ["sonde", "refus"])

    def test_les_lignes_ne_secrasent_pas(self):
        for index in range(3):
            self.entrepot.ecrire_journal({"quoi": "sonde-%d" % index})
        self.assertEqual(len(self.entrepot.lire_journal()), 3)


class TestPurge(BaseEntrepot):
    """R20 : purge d'un tenant, données absentes, preuve de purge."""

    def peupler(self):
        self.entrepot.ecrire("findings", {"id": "FINDING-2026-0001",
                                          "tenant_id": "TEN-acme"})
        self.entrepot.ecrire("campagnes", {"id": "CMP-0042",
                                           "tenant_id": "TEN-acme"})
        self.entrepot.ecrire("findings", {"id": "FINDING-2026-0002",
                                          "tenant_id": "TEN-autre"})

    def test_purge_et_preuve(self):
        self.peupler()
        preuve = self.entrepot.supprimer_tenant("TEN-acme")
        self.assertEqual(self.entrepot.lister("findings", tenant_id="TEN-acme"), [])
        self.assertEqual(self.entrepot.lister("campagnes", tenant_id="TEN-acme"), [])
        self.assertTrue(preuve.id.startswith("PRV-"))
        self.assertEqual(preuve.type, "purge")
        self.assertTrue(preuve.empreinte.startswith("sha256:"))

    def test_autre_tenant_intact(self):
        self.peupler()
        self.entrepot.supprimer_tenant("TEN-acme")
        reste = self.entrepot.lister("findings", tenant_id="TEN-autre")
        self.assertEqual([f["id"] for f in reste], ["FINDING-2026-0002"])

    def test_preuve_de_purge_sur_disque(self):
        self.peupler()
        preuve = self.entrepot.supprimer_tenant("TEN-acme")
        self.assertTrue(os.path.isfile(preuve.chemin))
        with open(preuve.chemin, encoding="utf-8") as f:
            contenu = json.load(f)
        self.assertIn("FINDING-2026-0001", contenu["supprimes"]["findings"])

    def test_purge_d_un_tenant_inexistant(self):
        preuve = self.entrepot.supprimer_tenant("TEN-fantome")
        self.assertEqual(preuve.type, "purge")


if __name__ == "__main__":
    unittest.main()
