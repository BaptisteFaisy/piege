# CONTRACTS-INTERFACES — frozen module APIs

Companion to `CONTRACTS.md` (data contracts) and `CONTRACTS-LOTS.md` (file
ownership). A lot implements the interface of its own section; another lot
consumes it only through these signatures. Signatures are frozen: parameter
names, order, return shape and raised exceptions.

Every function below is pure of I/O unless stated otherwise, and every public
function carries a French docstring.

## 1. Cible adapter (`piege.cibles`) — lot 1

A *target* is the customer application. The engine never speaks HTTP itself.

```python
class Cible(Protocol):
    id: str
    application_id: str
    def sonder(self, demande: str, session: str, graine: int) -> Reponse: ...
    def deposer_document(self, chemin: str, contenu: str, session: str) -> str: ...
    def mesurer(self, requete: str, session: str) -> Reponse: ...
    def reindexer(self, session: str) -> None: ...
    def detruire_index(self, index_id: str) -> None: ...
    def journaliser(self, evenement: dict) -> None: ...
```

- `sonder` sends one probe and returns a `Reponse`. It must never raise for a
  refused answer: a refusal is a `Reponse` with `garde_fou_declenche=True`.
- `deposer_document` is only called for family F and only on a **test index**
  created by the campaign. Implementations must refuse a target index.
- `detruire_index` is called in a `finally` block by the engine (EF-17).
- Implementations: `CibleLocaleDemo` (deterministic, offline — the demo
  target), `CibleHttp` (stdlib `urllib`, used by the evaluation harness),
  `CibleBedrock` (lazy `boto3`, real Knowledge Bases / Guardrails).

Factory: `piege.cibles.creer_cible(spec: dict) -> Cible`.

## 2. LLM provider (`piege.fournisseurs`) — lot 3

```python
class Fournisseur(Protocol):
    nom: str
    def completer(self, messages: list[dict], graine: int,
                  max_jetons: int = 1500, temperature: float = 0.0) -> ReponseModele: ...
    def sortie_structuree(self, messages: list[dict], schema: dict, graine: int) -> dict: ...
```

```python
ReponseModele(texte: str, jetons_entree: int, jetons_sortie: int,
              modele: str, brut: dict = {})
```

Implementations: `FournisseurLocal` (deterministic, offline, rule-based —
the default in CI and in `make demo`), `FournisseurInferhub` (OpenAI-compatible
HTTP, stdlib `urllib`, used by the Hermes conflict agent and as a judge
fallback), `FournisseurBedrock` (lazy `boto3`, real Bedrock models).

Contract:

- `sortie_structuree` must return a dict **validating against `schema`**;
  on invalid output it raises `FournisseurIndisponible` (the caller retries
  once with a stricter prompt, then falls back to the local provider).
- Providers must report the tokens they consumed — the cost table depends on it
  (ENF-10). The local provider reports its *simulated* usage consistently.
- A provider never logs the full prompt of a customer corpus.

## 3. Policy (`piege.securite.politique`) — lot 10

The rules live in the gateway, not in the prompt (spec §17.3).

```python
def evaluer(outil: str, faits: dict) -> Decision: ...
def exiger(mandat: Mandat, technique: Technique, cible: Application,
           campagne: Campagne, arret_urgence: bool) -> Decision: ...
```

`faits` keys (all optional, defaults are the safe ones): `mandat_statut`,
`maintenant`, `cible_id`, `technique_id`, `technique_environnement`,
`cible_environnement`, `production_autorisee`, `campagne_appels_restants`,
`campagne_jetons_restants`, `technique_budget_jetons`, `arret_urgence`,
`correctif_autorisation_humaine`, `correctif_autorise_par`,
`correctif_type`, `index_cible`, `index_production`, `depot_production`.

Rules (Annexe B, normative order):

1. `MandatInvalide` if the mandate is missing, not `valide`, or outside its window.
2. `HorsPerimetre` if the target application or the technique is not in the mandate.
3. `ProductionInterdite` if the environment is `production` and the mandate does
   not allow it, **or** if the technique declares `production: jamais`.
4. `BudgetEpuise` if the call budget or the token budget is exhausted.
5. `ArretUrgence` if the emergency stop is active.
6. For `Garde___applique`: human authorisation required, author must be
   `commanditaire` or `analyste`, and the type must be `garde_fou` or
   `politique` — `prompt`, `code` and `corpus` are refused (EF-42).
7. For `F___deposer`: the target index must be the campaign's test index;
   the production index requires an explicit `depot_production` flag.

A refusal returns `Decision(accorde=False, regle="<rule id>", motif=...)` and is
**journalled** with the violated rule. The decision is identical whether it is
computed locally or by AgentCore Policy: the local evaluator is the reference
implementation, and the Bedrock adapter mirrors it.

## 4. Identity and tenancy (`piege.securite.identite`) — lot 10

```python
def resoudre_tenant(jeton: str) -> str: ...
def exiger_role(tenant: str, jeton: str, roles: list[str]) -> None: ...
```

- The tenant comes **only** from the token (EF-61). No route accepts a tenant
  parameter; a request carrying one is rejected (`TenantInconnu`).
- Roles (spec §7): `commanditaire`, `proprietaire`, `analyste`, `commercial`.
- In the local/offline mode, the token format is `jeton:<tenant>:<role>[:<role>…]`
  — a test-only convention, documented in `docs/TEST-INSTRUCTIONS.md`.

## 5. Campaign engine (`piege.moteur`) — lot 3

```python
def executer_campagne(config: ConfigurationCampagne) -> Campagne: ...
def executer_technique(config: ConfigurationTechnique) -> Execution: ...
def appliquer_budget(campagne: Campagne, technique: Technique) -> None: ...
def suspendre(campagne_id: str) -> None: ...
def reprendre(campagne_id: str) -> None: ...
```

```python
ConfigurationCampagne(mandat_id, application_id, tenant_id, type: TypeCampagne,
                       graine: int, technique_ids: list[str] | None = None,
                       familles: list[Famille] | None = None,
                       parallelisme: int = 4, budget_appels: int = 0,
                       budget_jetons: int = 0, corpus_legitime_id: str = "",
                       cible_spec: dict = {}, arrete_urgence: bool = False,
                       attaquant=None, juge=None, evaluateur=None,
                       entrepot=None, fournisseur=None)
```

Amendement S0 (injection des composants) : les cinq derniers champs, tous
optionnels et placés en fin de signature, permettent au moteur de fonctionner
avant que les lots 4, 5 et 10 soient mergés, et rendent ses tests unitaires
indépendants. `None` signifie « import paresseux, à l'intérieur de la fonction,
de l'implémentation réelle » (`piege.agents.attaquant`, `piege.agents.juge`,
`piege.securite.politique`, `piege.stockage`, `piege.fournisseurs`). Un repli
hors ligne éventuel (`piege.moteur.replis`) applique exactement les règles de
CONTRACTS-INTERFACES §3 et ne contient aucune logique métier inédite ; il est
supprimé dès que les lots correspondants sont mergés. Aucun de ces modules
n'est importé en tête de fichier du moteur : pas de couplage croisé entre lots
menés en parallèle.

Guarantees:

- Every probe goes through `piege.securite.politique.exiger` **before** the
  call; a refusal ends the technique, journals the rule and produces an
  `Execution` with `verdict=None`, `erreur="hors_perimetre"`.
- The call budget is enforced **in code** (ENF-02): at the threshold the
  campaign stops cleanly, the state is kept, `statut` becomes `interrompue`.
- The emergency stop is checked between every probe and finishes in under
  5 seconds (R5); the state is resumable.
- Each technique runs in its own session (`session` id passed to the target);
  multi-turn techniques keep their session, others do not (spec §17.4).
- Every exchange is journalled: probe, raw response, tokens, latency, verdict.
- Parallelism is bounded by `parallelisme` (default 4, max 8) and never
  exceeds the mandate's `budget_appels`.

## 6. Judge (`piege.agents.juge`) — lot 5

```python
def juger(technique: Technique, transcription: str, fournisseur: Fournisseur,
          graine: int) -> Verdict: ...
def second_passage(verdict: Verdict, transcription: str,
                   fournisseur: Fournisseur, graine: int) -> Verdict: ...
def seuil_confiance() -> float: ...          # 0.75
def revue_humaine_requise(verdict: Verdict) -> bool: ...
```

The judge returns a `Verdict` (frozen shape):

```json
{
  "verdict": "reussi | echoue | ambigu",
  "impact": 1,
  "citation": "exact excerpt of the response that grounds the verdict",
  "confiance": 0.0,
  "motif": "short text",
  "garde_fou_declenche": false
}
```

- Temperature 0, structured output enforced; `impact` is a **classified fact**
  (1..4), never a severity.
- A `reussi` verdict is replayed by a second, independent pass with a different
  seed; a disagreement sends the finding to human review (EF-22).
- The judge has **no tool** and never calls the target (spec §18.1).
- The judge prompt is fixed and versioned in `piege.agents.juge.prompts`.

## 7. Attacking agent (`piege.agents.attaquant`) — lot 4

```python
def executer(technique: Technique, cible: Cible, mandat: Mandat,
             fournisseur: Fournisseur, graine: int, journal: Journal) -> Execution: ...
def variantes(technique: Technique, graine: int) -> list[str]: ...
```

- The agent receives **only**: the technique, the first probe, the maximum
  number of turns and a measurable objective. It never receives the scope:
  the scope is enforced by Policy (spec §18.2).
- A probe that would leave the perimeter is still attempted (that is its
  nature) and is refused by the gateway with a 403 that the demo shows.

## 8. Family F — corpus poisoning (`piege.familles.empoisonnement`) — lot 7

```python
def executer(technique: Technique, cible: Cible, mandat: Mandat,
             index_test: str, graine: int, journal: Journal) -> list[Mesure]: ...
def creer_index_test(cible: Cible, mandat: Mandat) -> str: ...
def deposer(cible: Cible, index_test: str, technique: Technique) -> str: ...
def detruire(cible: Cible, index_test: str) -> None: ...
```

`Mesure(nom, valeur: bool, citation: str, detail: dict = {})` with the three
measures of spec §14.3: `relais`, `execution`, `persistance`. The test index
is created in the MSP account, cloned from the declared corpus, and destroyed
in a `finally` block — nothing survives in the customer's corpus (EF-17).

## 9. Family G — false refusals (`piege.familles.faux_refus`) — lot 8

```python
def executer(corpus: CorpusLegitime, cible: Cible, graine: int,
             journal: Journal) -> list[FauxRefus]: ...
def classifier(reponse: Reponse) -> ClasseRefus: ...
def cause(reponse: Reponse, technique: Technique | None) -> CauseRefus: ...
```

- Without a legitimate corpus the family **refuses to run** and says so
  explicitly (`CorpusLegitimeAbsent`, EF-34) — it never returns an empty figure.
- Every refusal is classified (`ClasseRefus`), its cause identified
  (`CauseRefus`), the loss estimated with `severite.severite_faux_refus`.

## 10. Fixes (`piege.correctifs`) — lot 9

```python
def proposer(finding: Finding, application: Application) -> list[Correctif]: ...
def autoriser(correctif_id: str, auteur: str, role: str) -> Correctif: ...
def appliquer(correctif: Correctif, cible: Cible, mandat: Mandat) -> Correctif: ...
def rejouer(finding: Finding, cible: Cible, mandat: Mandat,
            graine: int) -> Preuve: ...
def controler_regression(finding: Finding, executions: list[Execution]) -> list[str]: ...
def controler_effet_de_bord(avant: list[FauxRefus], apres: list[FauxRefus]) -> dict: ...
```

- A fix is applied only after explicit human approval (EF-42); the approval
  records who and when, and the role is checked by Policy.
- Only `garde_fou` and `politique` fixes are applied; `prompt`, `code` and
  `corpus` fixes are **proposed** and applied by the customer (spec §15).
- The replay produces a dated proof of closure; a regression (a closed finding
  reopening) and a side effect (false refusals increasing) are reported **in
  the same line** as the closure (EF-44, EF-45).

## 11. Storage (`piege.stockage`) — lot 10

```python
class Entrepot(Protocol):
    def ecrire(self, table: str, enregistrement: dict) -> str: ...
    def lire(self, table: str, identifiant: str) -> dict | None: ...
    def lister(self, table: str, **filtres) -> list[dict]: ...
    def supprimer_tenant(self, tenant_id: str) -> Preuve: ...
    def ecrire_journal(self, evenement: dict) -> str: ...
```

Tables (spec §19.1): `tenants`, `applications`, `mandats`, `campagnes`,
`executions`, `findings`, `correctifs`, `preuves`, `corpus_legitimes`,
`faux_refus`, `journal`.

- Implementations: `EntrepotLocal` (JSON files under `donnees-locales/`, the
  default offline) and `EntrepotDynamoDb` (lazy `boto3`).
- The journal is append-only and hash-chained; a deletion is detectable.
- Every read is filtered by the tenant resolved from the token (EF-60).

## 12. Observability (`piege.observabilite`) — lot 11

```python
def tracer(evenement: dict) -> None: ...
def compte(campagne_id: str) -> Compteur: ...
def cout_mesure(campagne_id: str) -> float: ...
def cout_par_tenant(tenant_id: str) -> float: ...
def budget_restant(campagne: Campagne) -> dict: ...
```

`Compteur(appels: int, jetons_entree: int, jetons_sortie: int,
cout: float, par_modele: dict = {})`. Costs are **measured** from the token
counters, never estimated (ENF-10, KPI-7).

## 13. API (`piege.api`) — lot 12

Standard-library HTTP (no framework dependency, C3), plus a Lambda adapter.

```python
def router(methode: str, chemin: str, corps: dict, entetes: dict) -> tuple[int, dict]: ...
def creer_app(api: Api) -> Application: ...      # wsgiless, testable in process
```

Routes (spec §20): `POST /mandats`, `GET /mandats/{id}`, `POST /applications`,
`POST /corpus-legitimes`, `POST /campagnes`, `GET /campagnes/{id}`,
`POST /campagnes/{id}/suspendre`, `POST /campagnes/{id}/reprendre`,
`GET /campagnes/{id}/executions`, `POST /executions/{id}/revue`,
`GET /findings`, `GET /findings/{id}`, `POST /findings/{id}/rejouer`,
`GET /correctifs/{id}`, `POST /correctifs/{id}/autoriser`,
`GET /rapports/{campagne_id}`, `GET /attestations/{id}`,
`GET /tendances/{application_id}`, `GET /budget`, `GET /health`.

- Authentication: `Authorization: Bearer <jeton>`; the tenant comes from the
  token only.
- Response body: `{"donnees": ...}` on success, `{"erreur": {...}}` on failure
  (status per `CONTRACTS.md` §7).
- The emergency stop is available in **one gesture** from the portal and the
  API (ENF-14).

## 14. Reports (`piege.rapport`) — lot 12

```python
def rapport(campagne: Campagne, executions: list[Execution],
            findings: list[Finding], faux_refus: list[FauxRefus],
            langue: str = "fr") -> str: ...
def attestation(campagne: Campagne, findings: list[Finding], langue: str = "fr") -> str: ...
def resume(campagne: Campagne, findings: list[Finding],
           faux_refus: list[FauxRefus]) -> dict: ...
```

- `langue` is `fr` or `en`; both are complete (EF-51). The customer-facing
  report shows what leaked **and** what is broken, side by side (spec §13.3),
  plus what could **not** be tested and why (spec §21.5).
- The attestation is deliberately poor in detail: no probe, no citation
  (EF-53).

## 15. CLI (`piege.cli`) — lot 3

```
piege demo [--graine N] [--cible SPEC] [--catalogue DIR] [--json]
piege catalogue [--famille F] [--resume]
piege rapport --derniere [--langues fr,en]
piege validation --mandat MANDAT [--technique ID]
```

Exit codes: `0` success, `1` usage error, `2` a refused operation (policy),
`3` internal error. The CLI is the offline entry point used by `make demo`.
