"""Tests de l'export PDF/HTML (#88) et des notifications Slack/Teams (#84)."""

from __future__ import annotations

import unittest

from piege.notifications import (EVENEMENTS, construire, notifier,
                                 notifier_evenement)
from piege.notifications import slack, teams
from piege.notifications.webhooks import poster
from piege.rapport.export_pdf import (echapper_pdf, encoder_texte, export_html,
                                      export_pdf, markdown_vers_lignes)

RAPPORT = """# Rapport de campagne

## Synthèse

| Ce qui fuit | Ce qui est cassé |
|---|---|
| 2 critiques | 31 faux refus |

## Découvertes

### FINDING-2026-0147 — CRITIQUE
- Score : 32 (impact 4 × exploitabilité 4 × exposition 2)
- Preuve : « Niveau 1 : 32 400 EUR brut annuel »
"""


class TestExportPdf(unittest.TestCase):
    """#88 : un vrai PDF, en bibliothèque standard, sans dépendance."""

    def test_structure_pdf(self):
        pdf = export_pdf(RAPPORT, "Rapport Piège")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", pdf)
        self.assertIn(b"\nxref\n", pdf)
        self.assertIn(b"/Type /Catalog", pdf)
        self.assertIn(b"/BaseFont /Helvetica", pdf)

    def test_au_moins_une_page(self):
        pdf = export_pdf(RAPPORT)
        self.assertGreaterEqual(pdf.count(b"/Type /Page "), 1)

    def test_multipage(self):
        long = "\n".join("Ligne %d du rapport de sécurité." % i for i in range(200))
        pdf = export_pdf(long)
        self.assertGreater(pdf.count(b"/Type /Page "), 1)

    def test_xref_coherent(self):
        """startxref pointe bien vers la table xref."""
        pdf = export_pdf(RAPPORT)
        position = int(pdf.split(b"startxref\n")[1].split(b"\n")[0])
        self.assertEqual(pdf[position:position + 4], b"xref")

    def test_accentues(self):
        pdf = export_pdf("Rapport été à çà — sécurité")
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_echappement(self):
        pdf = export_pdf("Texte avec (parenthèses) et \\ antislash.")
        self.assertIn(b"\\(", pdf)
        self.assertIn(b"\\\\", pdf)

    def test_encoder_texte(self):
        # Les accents Latin-1 (WinAnsi) sont conservés ; le tiret long est remplacé.
        self.assertEqual(encoder_texte("été—à").decode("latin-1"), "été-à")
        self.assertEqual(encoder_texte("\u2019").decode("latin-1"), "'")

    def test_echapper_pdf(self):
        self.assertEqual(echapper_pdf("a(b)c"), r"a\(b\)c")
        self.assertEqual(echapper_pdf("a\\b"), "a\\\\b")

    def test_deterministe(self):
        self.assertEqual(export_pdf(RAPPORT), export_pdf(RAPPORT))

    def test_vide(self):
        pdf = export_pdf("")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))


class TestMarkdownVersLignes(unittest.TestCase):
    """Aplatissement du Markdown en texte imprimable."""

    def test_titres(self):
        lignes = markdown_vers_lignes("# Titre\n## Section")
        self.assertEqual(lignes[0], "TITRE")
        self.assertIn("SECTION", lignes)

    def test_tableau(self):
        lignes = markdown_vers_lignes("| a | b |\n|---|---|")
        self.assertTrue(any("a | b" in l for l in lignes))

    def test_puce(self):
        lignes = markdown_vers_lignes("- élément")
        self.assertIn("  - élément", lignes)

    def test_separateur_tableau_vide(self):
        lignes = markdown_vers_lignes("|---|---|")
        self.assertIn("", lignes)


class TestExportHtml(unittest.TestCase):
    """Version HTML imprimable (mise en forme complète)."""

    def test_structure(self):
        html = export_html(RAPPORT, "Rapport", "fr")
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<h1>", html)
        self.assertIn("lang='fr'", html)

    def test_echappement_html(self):
        html = export_html("# Titre <script>alert(1)</script>")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_tableau_et_liste(self):
        html = export_html("| a | b |\n- puce")
        self.assertIn("class='tab'", html)
        self.assertIn("<li>", html)


class TestEvenements(unittest.TestCase):
    """#84 : événements normalisés, sans donnée sensible."""

    def test_evenements_connus(self):
        self.assertIn("finding_critique", EVENEMENTS)
        self.assertIn("approbation_demandee", EVENEMENTS)

    def test_construction(self):
        ev = construire("finding_critique",
                        {"finding_id": "FINDING-2026-0147", "tenant_id": "TEN"},
                        base_url="https://piege.exemple")
        self.assertEqual(ev["type"], "finding_critique")
        self.assertEqual(ev["severite"], "critique")
        self.assertIn("FINDING-2026-0147", ev["lien"])

    def test_evenement_inconnu(self):
        with self.assertRaises(ValueError):
            construire("inconnu", {})

    def test_aucune_citation(self):
        """Une citation passée en données ne fuit pas dans le message."""
        ev = construire("finding_critique",
                        {"finding_id": "F-1", "citation": "Niveau 1 : 32 400 EUR"})
        self.assertNotIn("32 400", ev["texte"])
        self.assertNotIn("citation", ev["donnees"])

    def test_anglais(self):
        ev = construire("campagne_terminee", {"campagne_id": "CMP-1"}, langue="en")
        self.assertEqual(ev["titre"], "Campaign complete")

    def test_lien_approbation(self):
        ev = construire("approbation_demandee", {"correctif_id": "COR-1"},
                        base_url="https://x")
        self.assertIn("#correctif/COR-1", ev["lien"])


class TestSlackTeams(unittest.TestCase):
    """Projection Slack (Block Kit) et Teams (MessageCard)."""

    def evenement(self):
        return construire("finding_critique", {"finding_id": "F-1"},
                          base_url="https://piege.exemple")

    def test_payload_slack(self):
        charge = slack.payload(self.evenement())
        self.assertIn("blocks", charge)
        self.assertEqual(charge["blocks"][0]["type"], "header")
        self.assertTrue(any(b["type"] == "actions" for b in charge["blocks"]))

    def test_payload_teams(self):
        charge = teams.payload(self.evenement())
        self.assertEqual(charge["@type"], "MessageCard")
        self.assertIn("potentialAction", charge)

    def test_envoi_slack_transport_injecte(self):
        recus = []

        def transport(url, charge):
            recus.append((url, charge))
            return True

        self.assertTrue(slack.envoyer("https://hooks.slack/x", self.evenement(),
                                      transport))
        self.assertEqual(recus[0][0], "https://hooks.slack/x")

    def test_envoi_teams_transport_injecte(self):
        recus = []
        self.assertTrue(teams.envoyer("https://teams/x", self.evenement(),
                                      lambda u, c: recus.append((u, c)) or True))
        self.assertEqual(recus[0][0], "https://teams/x")

    def test_url_vide(self):
        self.assertFalse(slack.envoyer("", self.evenement()))
        self.assertFalse(teams.envoyer("", self.evenement()))


class TestDispersion(unittest.TestCase):
    """Dispersion multi-canaux, best-effort, hors ligne."""

    def evenement(self):
        return construire("campagne_terminee", {"campagne_id": "CMP-1"})

    def test_notifier_multi_canaux(self):
        recus = []

        def transport(url, charge):
            recus.append(url)
            return True

        config = {"slack": "https://s", "teams": "https://t",
                  "webhook": "https://w"}
        resultat = notifier(self.evenement(), config, transport)
        self.assertEqual(set(resultat), {"slack", "teams", "webhook"})
        self.assertTrue(all(resultat.values()))
        self.assertEqual(len(recus), 3)

    def test_canal_absent_ignore(self):
        resultat = notifier(self.evenement(), {"slack": "https://s"},
                            lambda u, c: True)
        self.assertEqual(list(resultat), ["slack"])

    def test_echec_ne_leve_pas(self):
        resultat = notifier(self.evenement(), {"slack": "https://s"},
                            lambda u, c: False)
        self.assertFalse(resultat["slack"])

    def test_config_vide(self):
        self.assertEqual(notifier(self.evenement(), {}), {})

    def test_notifier_evenement(self):
        recus = []
        notifier_evenement("arret_urgence", {"campagne_id": "CMP-1"},
                           {"webhook": "https://w"},
                           transport=lambda u, c: recus.append(c) or True)
        self.assertEqual(recus[0]["type"], "arret_urgence")

    def test_posteur_sans_url(self):
        self.assertFalse(poster("", {}))


if __name__ == "__main__":
    unittest.main()
