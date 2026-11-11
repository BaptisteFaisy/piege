"""Tests de la hiérarchie d'erreurs (CONTRACTS.md §7) — lot 0."""

from __future__ import annotations

import unittest

from piege import erreurs as e


class TestCodes(unittest.TestCase):
    """Chaque erreur de domaine porte un code stable et un statut HTTP."""

    def test_codes_uniques(self):
        classes = [getattr(e, nom) for nom in e.__all__
                   if isinstance(getattr(e, nom), type)
                   and issubclass(getattr(e, nom), e.ErreurPiege)
           ]
        codes = [c.code for c in classes]
        self.assertEqual(len(codes), len(set(codes)), codes)

    def test_table_http_complete(self):
        classes = [getattr(e, nom) for nom in e.__all__
                   if isinstance(getattr(e, nom), type)
                   and issubclass(getattr(e, nom), e.ErreurPiege)]
        for classe in classes:
            self.assertIn(classe.code, e.CODE_HTTP)
            self.assertEqual(e.CODE_HTTP[classe.code], classe.statut_http)

    def test_statuts_attendus(self):
        self.assertEqual(e.MandatExpire.statut_http, 403)
        self.assertEqual(e.BudgetEpuise.statut_http, 429)
        self.assertEqual(e.ArretUrgence.statut_http, 409)
        self.assertEqual(e.CorpusLegitimeAbsent.statut_http, 422)
        self.assertEqual(e.TechniqueInconnue.statut_http, 404)
        self.assertEqual(e.FournisseurIndisponible.statut_http, 502)


class TestCorpsErreur(unittest.TestCase):
    """Le corps d'erreur API est gelé : `{"erreur": {code, message, regle}}`."""

    def test_forme(self):
        erreur = e.HorsPerimetre("cible hors mandat", details={"regle": "perimetre.cible"})
        self.assertEqual(
            erreur.vers_dict(),
            {"erreur": {"code": "hors_perimetre", "message": "cible hors mandat",
                        "regle": "perimetre.cible"}})

    def test_regle_vide_par_defaut(self):
        self.assertEqual(e.BudgetEpuise("plus d'appels").vers_dict()["erreur"]["regle"], "")

    def test_message_porte(self):
        with self.assertRaises(e.ProductionInterdite) as ctx:
            raise e.ProductionInterdite("production interdite par le catalogue")
        self.assertIn("catalogue", str(ctx.exception))

    def test_heritage_mandat(self):
        self.assertTrue(issubclass(e.MandatExpire, e.MandatInvalide))
        self.assertTrue(issubclass(e.MandatInvalide, e.ErreurPiege))


if __name__ == "__main__":
    unittest.main()
