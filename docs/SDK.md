# Python SDK

A thin, standard-library client for the Piège API (`src/piege/sdk.py`). Same
surface as the HTTP routes of the specification (§20), no third-party
dependency, injectable transport for offline tests.

## Install

```bash
pip install -e .          # no dependency to resolve: the core is stdlib
```

## Authenticate

The tenant comes **only** from the token (`jeton:<tenant>:<role>` offline, or a
Cognito/AgentCore Identity token in production). No method accepts a tenant as a
parameter.

```python
from piege.sdk import Client, ErreurApi

client = Client("https://piege.example", "jeton:TEN-acme:analyste")
```

## Typical flow

```python
app = client.declarer_application(id="APP-guichet", nom="Guichet RH",
                                  type="rag", environnement="test", exposition=2,
                                  depot_document_autorise=True)
mandat = client.signer_mandat(application_id="APP-guichet",
                              perimetre_techniques=["A1", "C1", "F3"],
                              environnements=["test"],
                              fenetre_debut="2026-11-01T00:00:00Z",
                              fenetre_fin="2027-12-01T00:00:00Z",
                              budget_appels=40, budget_jetons=500000,
                              contact_urgence="security@customer.example")
campagne = client.lancer_campagne(mandat["mandat"]["id"], graine=20261124)

for finding in client.lister_findings(severite="critique"):
    correctifs = client.proposer_correctifs(finding["id"])
    garde_fou = next(c for c in correctifs if c["type"] == "garde_fou")
    bilan = client.autoriser_correctif(garde_fou["id"], auteur="anne.rssi",
                                       role="commanditaire")
    print(bilan["ligne"])       # closure + side effect, on one line

print(client.rapport(campagne["campagne"]["id"], langue="en")["rapport"])
```

## Methods

| Method | Route |
|---|---|
| `sante()` | `GET /health` |
| `declarer_application(**champs)` | `POST /applications` |
| `signer_mandat(**champs)` | `POST /mandats` |
| `mandat(id)` | `GET /mandats/{id}` |
| `charger_corpus_legitime(**champs)` | `POST /corpus-legitimes` |
| `lancer_campagne(mandat_id, graine, **champs)` | `POST /campagnes` |
| `campagne(id)` / `executions(id)` | `GET /campagnes/{id}` · `…/executions` |
| `suspendre(id)` / `reprendre(id)` | `POST /campagnes/{id}/suspendre` · `…/reprendre` |
| `trancher(execution_id, decision)` | `POST /executions/{id}/revue` |
| `lister_findings(**filtres)` / `finding(id)` | `GET /findings` · `GET /findings/{id}` |
| `proposer_correctifs(finding_id)` | `POST /findings/{id}/correctifs` |
| `autoriser_correctif(id, auteur, role)` | `POST /correctifs/{id}/autoriser` |
| `rejouer(finding_id)` | `POST /findings/{id}/rejouer` |
| `rapport(campagne_id, langue)` | `GET /rapports/{id}` |
| `attestation(campagne_id, langue)` | `GET /attestations/{id}` |
| `tendances(application_id)` / `budget()` | `GET /tendances/{id}` · `GET /budget` |

## Errors

Every 4xx/5xx raises `ErreurApi` with `.statut`, `.code`, `.message` and
`.regle` — the same domain codes as the API (e.g. `hors_perimetre`,
`mandat_expire`, `budget_epuise`). The token is never logged.

## Offline testing

Inject a transport to test without network:

```python
def faux_transport(methode, url, corps, entetes):
    return 200, '{"donnees": {"statut": "ok"}}'

client = Client("https://x", "jeton:TEN:analyste", transport=faux_transport)
```
