"""Tests du rapport client et de l'attestation : R15, R16, EF-50..EF-53."""

from __future__ import annotations

import unittest

from piege.rapport.attestation import attestation, compte_severites
from piege.rapport.rapport import (bloc_non_teste, rapport, resume)
from piege.rapport.synthese import (cle_dedoublonnage, construire_finding,
                                    synthetiser_findings)
from piege.rapport.traductions import LANGUES, LIBELLES, traduire
from piege.types import (Application, Campagne, Environnement, Execution,
                         Famille, FauxRefus, ClasseRefus, CauseRefus, Finding,
                         Severite, SeveriteRefus, StatutCampagne, StatutFinding,
                         TypeApplication, TypeCampagne, VerdictValeur,
                         fixer_horloge)

INSTANT = "2026-11-24T09:14:03Z"
CITATION = "Niveau 1 : 32 400 EUR brut annuel"


def campagne(**kw) -> Campagne:
    """Campagne terminée de référence."""
    valeurs = dict(id="CMP-0042", mandat_id="MAN-2026-0001",
                   application_id="APP-guichet", tenant_id="TEN-acme",
                   type=TypeCampagne.COMPLETE, graine=20261124,
                   statut=StatutCampagne.TERMINEE, debutee_le=INSTANT,
                   terminee_le=INSTANT, appels=12, jetons=48_000,
                   cout_mesure=3.31, techniques_prevues=["A1", "C1", "F3"],
                   techniques_executes=["A1", "C1", "F3"])
    valeurs.update(kw)
    return Campagne(**valeurs)


def application() -> Application:
    """Application cible de démonstration."""
    return Application(id="APP-guichet", tenant_id="TEN-acme",
                       nom="Guichet RH (démonstration)", type=TypeApplication.RAG,
                       acces="local://demo", modele="simule-local",
                       environnement=Environnement.TEST, exposition=2)


def execution(technique_id, verdict=VerdictValeur.REUSSI, impact=4,
              motif="grille divulguee", citation=CITATION) -> Execution:
    """Exécution jugée."""
    return Execution(id="EXE-%s" % technique_id, campagne_id="CMP-0042",
                     technique_id=technique_id, application_id="APP-guichet",
                     tenant_id="TEN-acme", statut="execute",
                     sondes_envoyees=["sonde"], reponse_brute="reponse",
                     jetons=3850, latence_ms=40, verdict=verdict, impact=impact,
                     confiance=0.95, citation=citation, motif=motif,
                     garde_fou_declenche=False, revue_humaine=False, graine=7)


def finding(**kw) -> Finding:
    """Découverte critique ouverte."""
    valeurs = dict(id="FINDING-2026-0147", application_id="APP-guichet",
                   tenant_id="TEN-acme", campagne_id="CMP-0042",
                   technique_ids=["A1"], famille=Famille.A,
                   severite=Severite.CRITIQUE, impact=4, exploitabilite=4,
                   exposition=2, score=32, statut=StatutFinding.OUVERT,
                   titre="Divulgation de la grille des salaires",
                   description="Surcharge d'instructions en un message.",
                   citation=CITATION, preuve_ids=["EXE-A1"], correctif_ids=[],
                   ouvert_le=INSTANT)
    valeurs.update(kw)
    return Finding(**valeurs)


def catalogue() -> dict:
    """Catalogue minimal : A1 (un tour) et C1 (deux tours, budget court)."""
    from piege.types import ProductionAutorisee, Technique

    def _t(identifiant, tours, appels):
        return Technique(id=identifiant, famille=Famille.A, nom=identifiant,
                         objectif="o", preconditions=[],
                         environnement=[Environnement.TEST],
                         production=ProductionAutorisee.SUR_MANDAT,
                         budget_appels=appels, tours_max=tours,
                         sonde_initiale="s", mesures=[], juge_reussi_si="r")

    return {"A1": _t("A1", 1, 2), "A8": _t("A8", 1, 2), "C1": _t("C1", 2, 3)}


def faux_refus(identifiant, frequence=9, criticite=4) -> FauxRefus:
    """Faux refus bloquant (déclaration d'accident du travail)."""
    return FauxRefus(id=identifiant, campagne_id="CMP-0042",
                     application_id="APP-guichet", tenant_id="TEN-acme",
                     demande_id="DL-0001", reponse_ref="refus",
                     classe=ClasseRefus.REFUS, cause=CauseRefus.GARDE_FOU,
                     frequence_mensuelle=frequence, criticite_metier=criticite,
                     perte=frequence * criticite,
                     severite=SeveriteRefus.BLOQUANT)


class TestSynthese(unittest.TestCase):
    """EF-24 : dédoublonnage ; C5 : sévérité calculée par code."""

    def test_dedoublonnage(self):
        executions = [execution("A1"), execution("A8", motif="grille divulguee")]
        findings = synthetiser_findings(campagne(), executions, application())
        self.assertEqual(len(findings), 1)
        self.assertEqual(sorted(findings[0].technique_ids), ["A1", "A8"])
        self.assertEqual(len(findings[0].preuve_ids), 2)

    def test_cle_de_dedoublonnage(self):
        self.assertEqual(cle_dedoublonnage(execution("A1")),
                         cle_dedoublonnage(execution("A8")))
        self.assertNotEqual(cle_dedoublonnage(execution("A1")),
                            cle_dedoublonnage(execution("C1", impact=3,
                                                       motif="invite restituee")))

    def test_echecs_ignores(self):
        findings = synthetiser_findings(
            campagne(), [execution("A1", verdict=VerdictValeur.ECHOUE)],
            application())
        self.assertEqual(findings, [])

    def test_severite_calculee(self):
        findings = synthetiser_findings(campagne(), [execution("A1")],
                                        application(), catalogue())
        self.assertEqual(findings[0].severite, Severite.CRITIQUE)
        self.assertEqual(findings[0].score, 32)
        self.assertEqual(findings[0].exploitabilite, 4)

    def test_impact_non_etabli(self):
        findings = synthetiser_findings(
            campagne(), [execution("A1", impact=None)], application(), catalogue())
        self.assertEqual(findings[0].severite, Severite.INDETERMINEE)
        self.assertIsNone(findings[0].score)

    def test_sans_catalogue_indeterminee(self):
        """Sans catalogue, l'exploitabilité n'est pas devinée : revue humaine."""
        findings = synthetiser_findings(campagne(), [execution("A1")],
                                        application())
        self.assertIsNone(findings[0].exploitabilite)
        self.assertEqual(findings[0].severite, Severite.INDETERMINEE)

    def test_persistance_en_base(self):
        class Entrepot:
            def __init__(self):
                self.ecrits = []

            def ecrire(self, table, enregistrement):
                self.ecrits.append((table, enregistrement["id"]))
                return enregistrement["id"]

        entrepot = Entrepot()
        synthetiser_findings(campagne(), [execution("A1")], application(),
                             catalogue(), entrepot=entrepot)
        self.assertEqual(entrepot.ecrits[0][0], "findings")

    def test_construction_directe(self):
        construit = construire_finding([execution("A1")], campagne(),
                                       application(), catalogue(), sequence=3)
        self.assertEqual(construit.id, "FINDING-2026-0003")
        self.assertEqual(construit.famille, Famille.A)


class TestResume(unittest.TestCase):
    """Les chiffres du tableau de bord (KPI-1, KPI-2, KPI-5, KPI-7)."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_chiffres(self):
        executions = [execution("A1"), execution("C1"),
                      execution("F3", verdict=VerdictValeur.ECHOUE)]
        chiffres = resume(campagne(), [finding()], [faux_refus("R-1")], executions)
        self.assertEqual(chiffres["techniques_executes"], 3)
        self.assertEqual(chiffres["techniques_reussies"], 2)
        self.assertEqual(chiffres["taux_de_contournement"], round(2 / 3, 4))
        self.assertEqual(chiffres["critiques_ouverts"], 1)
        self.assertEqual(chiffres["perte_totale"], 36)
        self.assertEqual(chiffres["heures_perdues"], 1.8)
        self.assertEqual(chiffres["cout_mesure"], 3.31)

    def test_vide(self):
        chiffres = resume(campagne(), [], [], [])
        self.assertEqual(chiffres["taux_de_contournement"], 0.0)
        self.assertEqual(chiffres["findings"], 0)

    def test_findings_fermes_non_comptes(self):
        ferme = finding(statut=StatutFinding.FERME)
        chiffres = resume(campagne(), [ferme], [], [])
        self.assertEqual(chiffres["critiques_ouverts"], 0)
        self.assertEqual(chiffres["findings"], 1)


class TestRapport(unittest.TestCase):
    """EF-50, EF-51, R15 : rapport complet, FR et EN, avec citations."""

    def setUp(self):
        fixer_horloge(INSTANT)
        self.findings = [finding()]
        self.refus = [faux_refus("R-%d" % i) for i in range(31)]
        self.executions = [execution("A1"), execution("C1", impact=3,
                                                      motif="invite restituee")]

    def tearDown(self):
        fixer_horloge(None)

    def texte(self, langue="fr", **kw):
        return rapport(campagne(), self.executions, self.findings, self.refus,
                       langue=langue, application=application(), **kw)

    def test_structre_fr(self):
        texte = self.texte()
        for attendu in ("Rapport de campagne", "Synthèse", "Ce qui fuit",
                        "Ce qui est cassé", "Découvertes", "Faux refus",
                        "Coût mesuré"):
            self.assertIn(attendu, texte)

    def test_deux_colonnes_cote_a_cote(self):
        """Le tableau qui vend le service : fuites et cassures côte à côte."""
        texte = self.texte()
        self.assertIn("| Ce qui fuit | Ce qui est cassé |", texte)
        self.assertIn("31 faux refus", texte)
        self.assertIn("1 bloquant", texte)

    def test_citations_incluses(self):
        self.assertIn(CITATION, self.texte())

    def test_calcul_de_severite_expose(self):
        texte = self.texte()
        self.assertIn("Score : 32", texte)
        self.assertIn("CRITIQUE", texte)

    def test_r15_export_anglais(self):
        texte = self.texte("en")
        for attendu in ("Campaign report", "Executive summary", "What leaks",
                        "What is broken", "Findings", "False refusals",
                        "Measured cost", "Critical"):
            self.assertIn(attendu, texte)
        self.assertIn(CITATION, texte)

    def test_aucun_francais_dans_la_version_anglaise(self):
        texte = self.texte("en")
        for interdit in ("Ce qui fuit", "Découvertes", "Faux refus",
                         "Coût mesuré"):
            self.assertNotIn(interdit, texte)

    def test_non_teste_signale(self):
        texte = self.texte(non_testes=["motif_corpus_absent",
                                       "motif_hors_perimetre"])
        self.assertIn("Ce qui n'a pas pu être testé", texte)
        self.assertIn("Famille G non exécutable", texte)
        self.assertIn("Family G not runnable", self.texte(
            "en", non_testes=["motif_corpus_absent"]))

    def test_aucune_decouverte(self):
        texte = rapport(campagne(), [], [], [], langue="fr",
                        application=application())
        self.assertIn("Aucune découverte", texte)

    def test_aucun_faux_refus(self):
        texte = rapport(campagne(), self.executions, self.findings, [],
                        langue="fr", application=application())
        self.assertIn("Aucun faux refus mesuré", texte)

    def test_bloc_non_teste_vide(self):
        self.assertEqual(bloc_non_teste([], traduire), "")


class TestAttestation(unittest.TestCase):
    """EF-53, R16 : attestation datée, volontairement pauvre."""

    def setUp(self):
        fixer_horloge(INSTANT)

    def tearDown(self):
        fixer_horloge(None)

    def test_r16_sans_detail_exploitable(self):
        texte = attestation(campagne(), [finding().vers_dict()])
        self.assertNotIn(CITATION, texte)
        self.assertNotIn("Oublie", texte)
        self.assertNotIn("sonde", texte.lower())

    def test_contenu_minimal(self):
        texte = attestation(campagne(), [finding().vers_dict()])
        self.assertIn("CMP-0042", texte)
        self.assertIn("MAN-2026-0001", texte)
        self.assertIn("Attestation de test de sécurité", texte)
        self.assertIn("volontairement dépourvue", texte)

    def test_compteurs_seulement(self):
        texte = attestation(campagne(), [finding().vers_dict(),
                                         finding(id="F-2",
                                                 severite=Severite.ELEVE)
                                         .vers_dict()])
        self.assertIn("Découvertes : 2", texte)
        self.assertIn("Critique : 1", texte)
        self.assertIn("Élevé : 1", texte)

    def test_findings_fermes(self):
        texte = attestation(campagne(),
                            [finding(statut=StatutFinding.FERME).vers_dict()])
        self.assertIn("Fermé : 1", texte)

    def test_version_anglaise(self):
        texte = attestation(campagne(), [finding().vers_dict()], langue="en")
        self.assertIn("Security testing attestation", texte)
        self.assertIn("Findings : 1", texte)
        self.assertNotIn("Attestation de test", texte)

    def test_destinataire(self):
        texte = attestation(campagne(), [], destinataire="Assureur XYZ")
        self.assertIn("Assureur XYZ", texte)

    def test_compte_severites(self):
        compte = compte_severites([finding().vers_dict()])
        self.assertEqual(compte["critique"], 1)
        self.assertEqual(sum(compte.values()), 1)


class TestTraductions(unittest.TestCase):
    """Les deux langues sont strictement alignées (ENF-11)."""

    def test_cles_alignees(self):
        for cle, entree in LIBELLES.items():
            self.assertEqual(set(entree), set(LANGUES), cle)
            for langue in LANGUES:
                self.assertTrue(str(entree[langue]).strip(), cle)

    def test_traduction(self):
        self.assertEqual(traduire("synthese", "fr"), "Synthèse")
        self.assertEqual(traduire("synthese", "en"), "Executive summary")

    def test_cle_inconnue(self):
        self.assertEqual(traduire("cle_inconnue", "fr"), "cle_inconnue")

    def test_langue_inconnue_replie(self):
        self.assertEqual(traduire("synthese", "de"), "Synthèse")


if __name__ == "__main__":
    unittest.main()
