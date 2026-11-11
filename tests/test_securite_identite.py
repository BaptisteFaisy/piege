"""Tests d'identité : le tenant vient du jeton, jamais d'un paramètre."""

from __future__ import annotations

import unittest

from piege.erreurs import TenantInconnu
from piege.securite import identite


class TestJeton(unittest.TestCase):
    """Convention hors ligne `jeton:<tenant>:<role>[:<role>…]`."""

    def test_resolution_du_tenant(self):
        jeton = identite.jeton_test("TEN-acme", "commanditaire")
        self.assertEqual(identite.resoudre_tenant(jeton), "TEN-acme")

    def test_roles_multiples(self):
        jeton = identite.jeton_test("TEN-acme", "analyste", "commanditaire")
        self.assertEqual(identite.roles(jeton), ["analyste", "commanditaire"])

    def test_role_par_defaut(self):
        self.assertEqual(identite.roles(identite.jeton_test("TEN-acme")), ["analyste"])

    def test_role_inconnu_refuse(self):
        with self.assertRaises(TenantInconnu):
            identite.jeton_test("TEN-acme", "root")

    def test_jeton_absent(self):
        for vide in ("", None):
            with self.assertRaises(TenantInconnu):
                identite.resoudre_tenant(vide)

    def test_jeton_malforme(self):
        for mauvais in ("TEN-acme:analyste", "jeton:TEN-acme", "jeton::analyste"):
            with self.assertRaises(TenantInconnu):
                identite.resoudre_tenant(mauvais)


class TestRoles(unittest.TestCase):
    """Un rôle habilité est exigé pour agir (spécification §7)."""

    def test_role_habilite(self):
        jeton = identite.jeton_test("TEN-acme", "commanditaire")
        identite.exiger_role("TEN-acme", jeton, ["commanditaire", "analyste"])

    def test_role_non_habilite(self):
        jeton = identite.jeton_test("TEN-acme", "commercial")
        with self.assertRaises(TenantInconnu) as ctx:
            identite.exiger_role("TEN-acme", jeton, ["commanditaire"])
        self.assertEqual(ctx.exception.details["regle"], "identite.role")

    def test_tenant_incoherent(self):
        jeton = identite.jeton_test("TEN-acme", "analyste")
        with self.assertRaises(TenantInconnu) as ctx:
            identite.exiger_role("TEN-autre", jeton, ["analyste"])
        self.assertEqual(ctx.exception.details["regle"], "identite.tenant")

    def test_roles_du_contrat(self):
        self.assertEqual(identite.ROLES,
                         ("commanditaire", "proprietaire", "analyste", "commercial"))


class TestParametreInterdit(unittest.TestCase):
    """EF-61 : aucune route n'accepte un tenant en paramètre."""

    def test_tenant_en_parametre_refuse(self):
        for cle in identite.PARAMETRES_INTERDITS:
            with self.assertRaises(TenantInconnu):
                identite.refuser_tenant_en_parametre({cle: "TEN-acme"})

    def test_parametres_sains_acceptes(self):
        identite.refuser_tenant_en_parametre({"campagne_id": "CMP-1", "page": 2})
        identite.refuser_tenant_en_parametre(None)
        identite.refuser_tenant_en_parametre({})

    def test_regle_journalisable(self):
        with self.assertRaises(TenantInconnu) as ctx:
            identite.refuser_tenant_en_parametre({"tenant_id": "TEN-acme"})
        self.assertEqual(ctx.exception.details["regle"], "identite.parametre")


if __name__ == "__main__":
    unittest.main()
