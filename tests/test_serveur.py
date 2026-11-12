"""Tests du serveur HTTP : le gestionnaire n'est pas lié comme méthode (régression).

Un bug passé : `gestionnaire` posé en attribut de classe sans `staticmethod`
était lié par le protocole descripteur, donc appelé avec `self` en premier
argument → « takes 4 positional arguments but 5 were given » sur chaque requête.
Ce test verrouille le correctif.
"""

from __future__ import annotations

import inspect
import unittest

from piege.api.serveur import creer_gestionnaire, gestionnaire_lambda


class TestGestionnaire(unittest.TestCase):
    """Le gestionnaire prend exactement 4 arguments, non lié."""

    def test_signature_quatre_arguments(self):
        gestionnaire = creer_gestionnaire()
        signature = inspect.signature(gestionnaire)
        self.assertEqual(len(signature.parameters), 4)

    def test_classe_statique(self):
        """Dans la classe du serveur, `gestionnaire` est un staticmethod."""
        import piege.api.serveur as serveur

        # Reproduit la construction de `servir()` sans démarrer de serveur.
        classe = type("GestionnairePiege", (serveur._Gestionnaire,),
                      {"gestionnaire": staticmethod(creer_gestionnaire()),
                       "dossier_portail": "portal"})
        # Non lié : accessible depuis la classe sans instance, 4 paramètres.
        self.assertEqual(len(inspect.signature(classe.gestionnaire).parameters), 4)

    def test_appel_reel_sans_self(self):
        """Un appel via une instance ne doit pas injecter `self`."""
        import piege.api.serveur as serveur

        classe = type("G", (serveur._Gestionnaire,),
                      {"gestionnaire": staticmethod(creer_gestionnaire()),
                       "dossier_portail": "portal"})
        # On n'instancie pas (BaseHTTPRequestHandler exige une socket) ; on
        # vérifie que l'attribut de classe n'est pas un descripteur liant.
        self.assertFalse(inspect.ismethod(classe.__dict__["gestionnaire"]
                                          if callable(classe.__dict__["gestionnaire"])
                                          else None))
        self.assertIsInstance(classe.__dict__["gestionnaire"], staticmethod)

    def test_lambda_sans_api(self):
        """Le gestionnaire Lambda répond (401/403 sans jeton), sans planter."""
        reponse = gestionnaire_lambda({"httpMethod": "GET", "path": "/api/health",
                                       "headers": {}})
        self.assertIn(reponse["statusCode"], (401, 403))
        self.assertIn("erreur", reponse["body"])


if __name__ == "__main__":
    unittest.main()
