"""Tests de la famille G — faux refus : corpus, classification, mesure, synthèse."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from piege.erreurs import CorpusLegitimeAbsent, ValeurHorsPlage
from piege.familles.faux_refus import (MINIMUM_DEMANDES, charger_corpus,
                                       classifier, cause, depuis_donnees,
                                       est_justifie, executer,
                                       heures_perdues_totales, par_cause,
                                       par_criticite, par_severite,
                                       pertes_les_plus_fortes,
                                       refuser_sans_corpus, repartition, resume,
                                       taux_de_refus, valider_corpus)
from piege.types import (CauseRefus, ClasseRefus, Reponse, SeveriteRefus,
                         fixer_horloge)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DEMO = os.path.join(RACINE, "demo", "corpus-legitime", "demandes.json")
INSTANT = "2026-11-24T09:14:03Z"

REPONSE_COMPLETE = ("Le télétravail est possible deux jours par semaine après "
                    "trois mois d'ancienneté, sur accord du manager.")
REPONSE_REFUS = "Je ne peux pas répondre à cette demande. Contactez le service RH."
REPONSE_GARDE_FOU = "[garde-fou] Contenu filtré : sujet réservé."
REPONSE_PARTIELLE = "Je peux répondre partiellement : il manque le document de référence."
REPONSE_HORS_SUJET = "Je ne comprends pas votre demande, reformulez."


class CibleFictive:
    """Cible de test : refuse selon un motif configurable par demande."""

    def __init__(self, refus=None, garde_fou=None):
        self.refus = set(refus or [])
        self.garde_fou = set(garde_fou or [])
        self.appels: list[dict] = []

    def sonder(self, demande, session, graine):
        self.appels.append({"demande": demande, "session": session})
        if demande in self.garde_fou:
            return Reponse(texte=REPONSE_GARDE_FOU, garde_fou_declenche=True,
                           garde_fou_id="gf-1", session=session)
        if demande in self.refus:
            return Reponse(texte=REPONSE_REFUS, session=session)
        return Reponse(texte=REPONSE_COMPLETE, jetons_entree=800,
                       jetons_sortie=40, session=session)


def corpus(demandes=None, **kw) -> object:
    """Corpus synthétique conforme au format du contrat."""
    from piege.types import CorpusLegitime, DemandeLegitime

    items = demandes if demandes is not None else _demandes_par_defaut()
    valeurs = dict(id="CORP-test", application_id="APP-guichet",
                   tenant_id="TEN-acme",
                   demandes=[DemandeLegitime(**d) for d in items],
                   source="test", charge_le=INSTANT)
    valeurs.update(kw)
    return CorpusLegitime(**valeurs)


def _demandes_par_defaut() -> list[dict]:
    """50 demandes : 9 de criticité 4, 12 de 3, 18 de 2, 11 de 1."""
    items = []
    repartition = [(4, 9), (3, 12), (2, 18), (1, 11)]
    numero = 1
    for criticite, nombre in repartition:
        for _ in range(nombre):
            items.append({"id": "DL-%04d" % numero,
                          "texte": "Demande légitime numéro %d" % numero,
                          "criticite": criticite,
                          "frequence_mensuelle": max(1, criticite * 2),
                          "langue": "fr", "attendu": "une réponse complète",
                          "etiquette": "test"})
            numero += 1
    return items


class TestCorpus(unittest.TestCase):
    """Chargement et validation du corpus de demandes légitimes (EF-30)."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_minimum_exige(self):
        self.assertEqual(MINIMUM_DEMANDES, 50)

    def test_corpus_conforme(self):
        self.assertEqual(len(corpus().demandes), 50)

    def test_corpus_trop_court(self):
        with self.assertRaises(ValeurHorsPlage):
            valider_corpus(corpus(demandes=_demandes_par_defaut()[:10]))

    def test_corpus_vide(self):
        with self.assertRaises(CorpusLegitimeAbsent):
            valider_corpus(corpus(demandes=[]))

    def test_corpus_absent(self):
        with self.assertRaises(CorpusLegitimeAbsent):
            refuser_sans_corpus(None)

    def test_criticite_hors_plage(self):
        items = _demandes_par_defaut()
        items[0]["criticite"] = 9
        with self.assertRaises(ValeurHorsPlage):
            valider_corpus(corpus(demandes=items))

    def test_texte_vide(self):
        items = _demandes_par_defaut()
        items[0]["texte"] = "   "
        with self.assertRaises(ValeurHorsPlage):
            valider_corpus(corpus(demandes=items))

    def test_frequence_nulle(self):
        items = _demandes_par_defaut()
        items[0]["frequence_mensuelle"] = 0
        with self.assertRaises(ValeurHorsPlage):
            valider_corpus(corpus(demandes=items))

    def test_repartition(self):
        self.assertEqual(repartition(corpus()), {4: 9, 3: 12, 2: 18, 1: 11})

    def test_depuis_donnees(self):
        donnees = {"id": "CORP-x", "application_id": "APP", "tenant_id": "TEN",
                   "source": "test", "charge_le": INSTANT,
                   "demandes": _demandes_par_defaut()}
        charge = depuis_donnees(donnees)
        self.assertEqual(len(charge.demandes), 50)
        self.assertEqual(charge.demandes[0].criticite, 4)

    def test_depuis_donnees_illisible(self):
        with self.assertRaises(ValeurHorsPlage):
            depuis_donnees({"autre": 1})

    def test_fichier_absent(self):
        with self.assertRaises(CorpusLegitimeAbsent):
            charger_corpus("/chemin/inexistant-piege.json")

    def test_chargement_depuis_fichier(self):
        donnees = {"id": "CORP-f", "application_id": "APP", "tenant_id": "TEN",
                   "source": "test", "charge_le": INSTANT,
                   "demandes": _demandes_par_defaut()}
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "demandes.json")
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(donnees, f, ensure_ascii=False)
            self.assertEqual(len(charger_corpus(chemin).demandes), 50)

    @unittest.skipUnless(os.path.isfile(CORPUS_DEMO),
                         "corpus de démonstration du lot 1 absent")
    def test_corpus_de_demonstration(self):
        charge = charger_corpus(CORPUS_DEMO)
        self.assertEqual(len(charge.demandes), 50)
        self.assertEqual(repartition(charge), {4: 9, 3: 12, 2: 18, 1: 11})


class TestClassification(unittest.TestCase):
    """EF-32 : cinq classes, sept causes."""

    def reponse(self, texte, garde_fou=False):
        return Reponse(texte=texte, garde_fou_declenche=garde_fou,
                       garde_fou_id="gf-1" if garde_fou else "")

    def test_reponse_complete(self):
        self.assertEqual(classifier(self.reponse(REPONSE_COMPLETE)),
                         ClasseRefus.COMPLETE)

    def test_refus(self):
        self.assertEqual(classifier(self.reponse(REPONSE_REFUS)), ClasseRefus.REFUS)

    def test_refus_par_garde_fou(self):
        self.assertEqual(classifier(self.reponse(REPONSE_GARDE_FOU, True)),
                         ClasseRefus.REFUS)

    def test_refus_partiel(self):
        self.assertEqual(classifier(self.reponse(REPONSE_PARTIELLE)),
                         ClasseRefus.REFUS_PARTIEL)

    def test_hors_sujet(self):
        self.assertEqual(classifier(self.reponse(REPONSE_HORS_SUJET)),
                         ClasseRefus.HORS_SUJET)

    def test_reponse_vide(self):
        self.assertEqual(classifier(self.reponse("")), ClasseRefus.HORS_SUJET)

    def test_reponse_tres_courte(self):
        self.assertEqual(classifier(self.reponse("Oui.")), ClasseRefus.PARTIELLE)

    def test_cause_garde_fou(self):
        self.assertEqual(cause(self.reponse(REPONSE_GARDE_FOU, True)),
                         CauseRefus.GARDE_FOU)

    def test_cause_corpus_absent(self):
        reponse = self.reponse("Je n'ai pas trouvé d'information dans les documents.")
        self.assertEqual(cause(reponse), CauseRefus.CORPUS_ABSENT)

    def test_cause_theme_trop_large(self):
        reponse = self.reponse("Cette demande porte sur un sujet réservé.")
        self.assertEqual(cause(reponse), CauseRefus.THEME_TROP_LARGE)

    def test_cause_modele(self):
        self.assertEqual(cause(self.reponse(REPONSE_HORS_SUJET)), CauseRefus.MODELE)

    def test_cause_autre(self):
        self.assertEqual(cause(self.reponse(REPONSE_REFUS)), CauseRefus.AUTRE)

    def test_refus_justifie(self):
        reponse = self.reponse(REPONSE_REFUS)
        self.assertTrue(est_justifie(reponse, "un refus est attendu ici"))
        self.assertFalse(est_justifie(reponse, "une réponse complète"))
        self.assertFalse(est_justifie(self.reponse(REPONSE_COMPLETE), "refus"))


class TestExecution(unittest.TestCase):
    """EF-31, EF-33 : exécution du corpus et chiffrage de la perte."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_aucun_refus(self):
        refus = executer(corpus(), CibleFictive(), 7, None, "CMP-1")
        self.assertEqual(refus, [])

    def test_refus_mesures(self):
        items = _demandes_par_defaut()
        cibles = {items[0]["texte"], items[1]["texte"]}
        refus = executer(corpus(items), CibleFictive(refus=cibles), 7, None,
                         "CMP-1")
        self.assertEqual(len(refus), 2)
        self.assertEqual({r.demande_id for r in refus},
                         {items[0]["id"], items[1]["id"]})

    def test_perte_et_severite(self):
        items = _demandes_par_defaut()
        refus = executer(corpus(items), CibleFictive(refus={items[0]["texte"]}),
                         7, None, "CMP-1")
        enregistrement = refus[0]
        self.assertEqual(enregistrement.perte,
                         items[0]["frequence_mensuelle"] * items[0]["criticite"])
        self.assertEqual(enregistrement.severite, SeveriteRefus.BLOQUANT)

    def test_session_vierge_par_demande(self):
        items = _demandes_par_defaut()[:5]
        cible = CibleFictive()
        executer(corpus(items), cible, 7, None, "CMP-1")
        sessions = [a["session"] for a in cible.appels]
        self.assertEqual(len(set(sessions)), len(sessions))

    def test_determinisme(self):
        items = _demandes_par_defaut()[:5]
        premier = executer(corpus(items), CibleFictive(refus={items[0]["texte"]}),
                           7, None, "CMP-1")
        second = executer(corpus(items), CibleFictive(refus={items[0]["texte"]}),
                          7, None, "CMP-1")
        self.assertEqual([r.vers_dict() for r in premier],
                         [r.vers_dict() for r in second])

    def test_refus_justifie_non_compte(self):
        items = _demandes_par_defaut()[:3]
        items[0]["attendu"] = "un refus est attendu"
        refus = executer(corpus(items), CibleFictive(refus={items[0]["texte"]}),
                         7, None, "CMP-1")
        self.assertEqual(refus, [])

    def test_taux_de_refus(self):
        items = _demandes_par_defaut()
        ensemble = corpus(items)
        refus = executer(ensemble, CibleFictive(refus={items[0]["texte"]}), 7,
                         None, "CMP-1")
        self.assertEqual(taux_de_refus(ensemble, refus), round(1 / 50, 4))
        self.assertEqual(taux_de_refus(None, []), 0.0)

    def test_corpus_absent_refuse(self):
        with self.assertRaises(CorpusLegitimeAbsent):
            executer(corpus(demandes=[]), CibleFictive(), 7, None, "CMP-1")

    def test_journal(self):
        class Journal:
            def __init__(self):
                self.lignes = []

            def consigner(self, qui, quoi, tenant, details=None, **kw):
                self.lignes.append((qui, quoi, details or {}))

        journal = Journal()
        items = _demandes_par_defaut()[:3]
        executer(corpus(items), CibleFictive(), 7, journal, "CMP-1")
        self.assertEqual(journal.lignes[0][1], "corpus_execute")
        self.assertEqual(journal.lignes[0][2]["demandes"], 3)


class TestSynthese(unittest.TestCase):
    """Le chiffre qui vend le service : perte, heures, priorités."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self.items = _demandes_par_defaut()
        refus_textes = {self.items[0]["texte"], self.items[9]["texte"],
                        self.items[20]["texte"]}
        self.refus = executer(corpus(self.items),
                              CibleFictive(refus=refus_textes), 7, None, "CMP-1")

    def tearDown(self):
        fixer_horloge(None)

    def test_par_criticite(self):
        compte = par_criticite(self.refus)
        self.assertEqual(sum(compte.values()), len(self.refus))

    def test_par_cause(self):
        compte = par_cause(self.refus)
        self.assertEqual(sum(compte.values()), len(self.refus))
        self.assertEqual(compte["autre"], len(self.refus))

    def test_par_severite(self):
        compte = par_severite(self.refus)
        self.assertEqual(sum(compte.values()), len(self.refus))
        self.assertGreaterEqual(compte["bloquant"], 1)

    def test_heures_perdues(self):
        attendu = round(sum(r.frequence_mensuelle * r.minutes_manuelles / 60
                            for r in self.refus), 2)
        self.assertEqual(heures_perdues_totales(self.refus), attendu)

    def test_top_pertes(self):
        top = pertes_les_plus_fortes(self.refus, limite=2)
        self.assertEqual(len(top), 2)
        self.assertGreaterEqual(top[0]["perte"], top[1]["perte"])

    def test_resume_complet(self):
        donnees = resume(self.refus, corpus(self.items), "CMP-1")
        self.assertEqual(donnees["demandes_testees"], 50)
        self.assertEqual(donnees["faux_refus"], 3)
        self.assertEqual(donnees["taux_de_refus"], 0.06)
        self.assertTrue(donnees["corpus_disponible"])
        self.assertEqual(donnees["perte_totale"],
                         sum(r.perte for r in self.refus))
        self.assertIn("par_criticite", donnees)
        self.assertIn("top_pertes", donnees)

    def test_resume_sans_corpus(self):
        donnees = resume([], None, "CMP-1")
        self.assertFalse(donnees["corpus_disponible"])
        self.assertEqual(donnees["taux_de_refus"], 0.0)


if __name__ == "__main__":
    unittest.main()
