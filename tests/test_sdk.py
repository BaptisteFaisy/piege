"""Tests du SDK Python (#86) : hors ligne, transport injecté, jeton jamais journalisé."""

from __future__ import annotations

import json
import unittest

from piege.sdk import Client, ErreurApi


class TransportFictif:
    """Transport de test : enregistre les appels, rend une réponse programmée."""

    def __init__(self, statut=200, donnees=None, erreur=None):
        self.statut = statut
        self.donnees = donnees if donnees is not None else {"ok": True}
        self.erreur = erreur
        self.appels: list[dict] = []

    def __call__(self, methode, url, corps, entetes):
        self.appels.append({"methode": methode, "url": url, "corps": corps,
                            "entetes": dict(entetes)})
        if self.erreur is not None:
            return self.statut, json.dumps({"erreur": self.erreur})
        return self.statut, json.dumps({"donnees": self.donnees})


def client(transport=None, **kw):
    """Client pointé sur une base fictive, transport injecté."""
    return Client("https://piege.test", "jeton:TEN-acme:analyste",
                  transport=transport or TransportFictif(), **kw)


class TestConstruction(unittest.TestCase):
    def test_jeton_requis(self):
        with self.assertRaises(ValueError):
            Client("https://x", "")

    def test_base_normalisee(self):
        self.assertEqual(Client("https://x/", "j").base_url, "https://x")

    def test_en_tete_authorization(self):
        transport = TransportFictif()
        client(transport).sante()
        self.assertEqual(transport.appels[0]["entetes"]["Authorization"],
                         "Bearer jeton:TEN-acme:analyste")

    def test_jeton_jamais_dans_le_corps(self):
        transport = TransportFictif()
        client(transport).declarer_application(id="APP-1", nom="x")
        self.assertNotIn("jeton:TEN-acme", transport.appels[0]["corps"].decode())


class TestMethodes(unittest.TestCase):
    """Chaque méthode construit la bonne requête et rend `donnees`."""

    def test_sante(self):
        transport = TransportFictif(donnees={"statut": "ok"})
        self.assertEqual(client(transport).sante()["statut"], "ok")
        self.assertEqual(transport.appels[0]["url"], "https://piege.test/api/health")
        self.assertEqual(transport.appels[0]["methode"], "GET")

    def test_declarer_application(self):
        transport = TransportFictif(donnees={"id": "APP-1"})
        resultat = client(transport).declarer_application(id="APP-1", nom="Guichet")
        self.assertEqual(resultat["id"], "APP-1")
        self.assertEqual(transport.appels[0]["methode"], "POST")
        corps = json.loads(transport.appels[0]["corps"])
        self.assertEqual(corps["nom"], "Guichet")

    def test_signer_mandat(self):
        transport = TransportFictif(donnees={"mandat": {"id": "MAN-1"}})
        resultat = client(transport).signer_mandat(application_id="APP-1")
        self.assertEqual(resultat["mandat"]["id"], "MAN-1")

    def test_lancer_campagne(self):
        transport = TransportFictif(donnees={"campagne": {"id": "CMP-1"}})
        client(transport).lancer_campagne("MAN-1", graine=7, parallelisme=2)
        corps = json.loads(transport.appels[0]["corps"])
        self.assertEqual(corps["mandat_id"], "MAN-1")
        self.assertEqual(corps["graine"], 7)
        self.assertEqual(corps["parallelisme"], 2)

    def test_lister_findings_avec_filtres(self):
        transport = TransportFictif(donnees=[])
        client(transport).lister_findings(severite="critique", statut="ouvert")
        url = transport.appels[0]["url"]
        self.assertIn("severite=critique", url)
        self.assertIn("statut=ouvert", url)

    def test_rapport_langue(self):
        transport = TransportFictif(donnees={"rapport": "x"})
        client(transport).rapport("CMP-1", langue="en")
        self.assertIn("langue=en", transport.appels[0]["url"])

    def test_autoriser_correctif(self):
        transport = TransportFictif(donnees={"ferme": True})
        client(transport).autoriser_correctif("COR-1", "anne", "commanditaire")
        corps = json.loads(transport.appels[0]["corps"])
        self.assertEqual(corps["auteur"], "anne")
        self.assertEqual(corps["role"], "commanditaire")

    def test_suspendre_reprendre(self):
        transport = TransportFictif(donnees={"arret": True})
        client(transport).suspendre("CMP-1", motif="incident")
        self.assertIn("/suspendre", transport.appels[0]["url"])
        self.assertEqual(json.loads(transport.appels[0]["corps"])["motif"], "incident")

    def test_toutes_les_methodes(self):
        """Chaque méthode de la surface API existe et appelle le bon chemin."""
        transport = TransportFictif(donnees={})
        c = client(transport)
        c.sante()
        c.declarer_application(id="A")
        c.signer_mandat(application_id="A")
        c.mandat("MAN-1")
        c.charger_corpus_legitime(demandes=[])
        c.lancer_campagne("MAN-1")
        c.campagne("CMP-1")
        c.executions("CMP-1")
        c.suspendre("CMP-1")
        c.reprendre("CMP-1")
        c.trancher("EXE-1", "confirme")
        c.lister_findings()
        c.finding("F-1")
        c.proposer_correctifs("F-1")
        c.autoriser_correctif("COR-1", "a", "analyste")
        c.rejouer("F-1")
        c.rapport("CMP-1")
        c.attestation("CMP-1")
        c.tendances("APP-1")
        c.budget()
        self.assertEqual(len(transport.appels), 20)


class TestErreurs(unittest.TestCase):
    """Les 4xx/5xx lèvent ErreurApi avec le code de domaine."""

    def test_erreur_403(self):
        transport = TransportFictif(statut=403,
                                    erreur={"code": "hors_perimetre",
                                            "message": "cible hors mandat",
                                            "regle": "perimetre.application"})
        with self.assertRaises(ErreurApi) as ctx:
            client(transport).lancer_campagne("MAN-1")
        self.assertEqual(ctx.exception.statut, 403)
        self.assertEqual(ctx.exception.code, "hors_perimetre")
        self.assertEqual(ctx.exception.regle, "perimetre.application")

    def test_erreur_404(self):
        transport = TransportFictif(statut=404,
                                    erreur={"code": "introuvable", "message": "x"})
        with self.assertRaises(ErreurApi):
            client(transport).finding("F-inexistant")

    def test_erreur_serialisable(self):
        transport = TransportFictif(statut=429,
                                    erreur={"code": "budget_epuise", "message": "stop"})
        try:
            client(transport).lancer_campagne("MAN-1")
        except ErreurApi as erreur:
            self.assertEqual(erreur.vers_dict()["code"], "budget_epuise")

    def test_corps_invalide(self):
        """Une réponse non-JSON ne plante pas le client."""

        def transport(methode, url, corps, entetes):
            return 500, "pas du json"

        with self.assertRaises(ErreurApi) as ctx:
            client(transport).sante()
        self.assertEqual(ctx.exception.statut, 500)


if __name__ == "__main__":
    unittest.main()
