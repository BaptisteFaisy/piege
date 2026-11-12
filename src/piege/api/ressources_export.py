"""Piège — routes de restitution enrichie et d'intégration.

Exposent au portail : l'export PDF/HTML du rapport (#88), l'aperçu du garde-fou
Bedrock qu'un correctif produirait (#42), l'aperçu des notifications Slack/Teams
(#84) et les extraits d'intégration GitHub Action / SDK (#91/#86).

L'export PDF rend le document en base64 dans une réponse JSON : le routeur reste
fidèle à son contrat (toujours JSON), et le portail décode en Blob pour
proposer le téléchargement. Aucune dépendance tierce.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from piege.api.aides import exiger_role, lire, lire_ou_erreur
from piege.types import Correctif, Finding, depuis_dict

__all__ = ["ROUTES", "export_pdf_route", "export_html_route",
           "apercu_garde_fou", "apercu_notification", "integrations"]

SNIPPET_ACTION = """# .github/workflows/scan-piege.yml (dépôt client)
on:
  push:
    paths: ["prompts/**", "model.json", "corpus/**"]
jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: BaptisteFaisy/piege@v1
        with:
          api_url: ${{ vars.PIEGE_API_URL }}
          tenant_token: ${{ secrets.PIEGE_TOKEN }}
          techniques: "A1,C1,F3"
          comment: "true"
"""

SNIPPET_SDK = '''from piege.sdk import Client

client = Client("https://piege.exemple", "jeton:TEN-acme:analyste")
mandat = client.signer_mandat(application_id="APP-guichet",
                              perimetre_techniques=["A1", "C1", "F3"],
                              environnements=["test"],
                              fenetre_debut="2026-11-01T00:00:00Z",
                              fenetre_fin="2027-12-01T00:00:00Z",
                              budget_appels=40, budget_jetons=500000,
                              contact_urgence="securite@client.exemple")
campagne = client.lancer_campagne(mandat["mandat"]["id"], graine=20261124)
for finding in client.lister_findings(severite="critique"):
    correctifs = client.proposer_correctifs(finding["id"])
    garde_fou = next(c for c in correctifs if c["type"] == "garde_fou")
    bilan = client.autoriser_correctif(garde_fou["id"], auteur="anne.rssi",
                                       role="commanditaire")
    print(bilan["ligne"])
'''


def export_pdf_route(api: Any, tenant: str, roles: list, campagne_id: str,
                     requete: Optional[dict] = None, **_) -> dict:
    """Rend le rapport PDF en base64 (#88)."""
    from piege.rapport.export_pdf import export_pdf
    from piege.rapport.rapport import rapport_depuis_entrepot

    del roles
    langue = str((requete or {}).get("langue", "fr")).lower()
    langue = langue if langue in ("fr", "en") else "fr"
    lire_ou_erreur(api, "campagnes", campagne_id, tenant)
    markdown = rapport_depuis_entrepot(api.entrepot, campagne_id, tenant, langue)
    octets = export_pdf(markdown, "Rapport Piège %s" % campagne_id)
    return {"campagne_id": campagne_id, "langue": langue, "mime": "application/pdf",
            "nom": "rapport-piege-%s-%s.pdf" % (campagne_id, langue),
            "contenu_base64": base64.b64encode(octets).decode("ascii"),
            "octets": len(octets)}


def export_html_route(api: Any, tenant: str, roles: list, campagne_id: str,
                      requete: Optional[dict] = None, **_) -> dict:
    """Rend le rapport HTML imprimable (#88)."""
    from piege.rapport.export_pdf import export_html
    from piege.rapport.rapport import rapport_depuis_entrepot

    del roles
    langue = str((requete or {}).get("langue", "fr")).lower()
    langue = langue if langue in ("fr", "en") else "fr"
    lire_ou_erreur(api, "campagnes", campagne_id, tenant)
    markdown = rapport_depuis_entrepot(api.entrepot, campagne_id, tenant, langue)
    return {"campagne_id": campagne_id, "langue": langue, "mime": "text/html",
            "nom": "rapport-piege-%s-%s.html" % (campagne_id, langue),
            "html": export_html(markdown, "Rapport Piège %s" % campagne_id, langue)}


def apercu_garde_fou(api: Any, tenant: str, roles: list, corps: dict, **_) -> dict:
    """Spécification du garde-fou Bedrock qu'un correctif produirait (#42).

    Aperçu **pur** : rien n'est appliqué sur AWS (boto3 n'est pas requis). C'est
    la traduction exacte que `appliquer_garde_fou_bedrock` enverrait.
    """
    from piege.correctifs.guardrails_bedrock import (construire_garde_fou,
                                                     resume_garde_fou)
    from piege.types import StatutCorrectif, TypeCorrectif

    del roles
    corps = corps or {}
    correctif = _resoudre_correctif(api, tenant, corps)
    finding = _resoudre_finding(api, tenant, corps)
    spec = construire_garde_fou(correctif, finding)
    return {"correctif_id": correctif.id, "spec_bedrock": spec,
            "resume": resume_garde_fou(spec),
            "note": "Aperçu pur — aucune écriture AWS. L'application réelle exige "
                    "boto3, des identifiants et l'accord humain (lot 9)."}


def _resoudre_correctif(api: Any, tenant: str, corps: dict) -> Correctif:
    """Correctif depuis son id, ou construit à la volée pour l'aperçu."""
    correctif_id = str(corps.get("correctif_id", ""))
    if correctif_id:
        brut = lire_ou_erreur(api, "correctifs", correctif_id, tenant)
        return depuis_dict(Correctif, brut)
    from piege.types import StatutCorrectif, TypeCorrectif

    return Correctif(
        id="COR-apercu", finding_id=str(corps.get("finding_id", "")),
        application_id="", tenant_id=tenant,
        type=TypeCorrectif(str(corps.get("type", "garde_fou"))),
        contenu=str(corps.get("contenu",
                              "Garde-fou : bloquer la rémunération individuelle.")),
        effort=1, reduction_risque="forte", statut=StatutCorrectif.PROPOSE)


def _resoudre_finding(api: Any, tenant: str, corps: dict) -> Optional[Finding]:
    """Découverte liée, si un finding_id est fourni."""
    finding_id = str(corps.get("finding_id", ""))
    if not finding_id:
        return None
    brut = lire(api, "findings", finding_id, tenant)
    return depuis_dict(Finding, brut) if brut else None


def apercu_notification(api: Any, tenant: str, roles: list, corps: dict,
                        **_) -> dict:
    """Aperçu des charges Slack et Teams d'un événement (#84), sans envoi."""
    from piege.notifications import construire
    from piege.notifications import slack, teams

    del api, roles
    corps = corps or {}
    evenement = construire(str(corps.get("evenement", "finding_critique")),
                           corps.get("donnees") or {},
                           str(corps.get("langue", "fr")),
                           str(corps.get("base_url", "")))
    return {"evenement": evenement, "slack": slack.payload(evenement),
            "teams": teams.payload(evenement),
            "note": "Aperçu pur — aucun envoi. Aucune citation ni preuve n'est "
                    "incluse (minimisation)."}


def integrations(api: Any, tenant: str, roles: list, **_) -> dict:
    """Extraits d'intégration GitHub Action et SDK (#91/#86)."""
    del api, tenant, roles
    return {"github_action": SNIPPET_ACTION, "sdk": SNIPPET_SDK,
            "doc_action": "docs/GITHUB-ACTION.md", "doc_sdk": "docs/SDK.md"}


ROUTES = [
    ("GET", "/rapports/{campagne_id}/pdf", export_pdf_route),
    ("GET", "/rapports/{campagne_id}/html", export_html_route),
    ("POST", "/guardrails/apercu", apercu_garde_fou),
    ("POST", "/notifications/apercu", apercu_notification),
    ("GET", "/integrations", integrations),
]
