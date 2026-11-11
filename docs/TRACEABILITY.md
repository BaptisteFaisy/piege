# TRACEABILITY — requirements ↔ code ↔ tests

Append-only: a lot adds its own rows and never rewrites another lot's.
Identifiers come from `docs/spec/cahier-des-charges.fr.md`.

## Functional requirements (EF-*)

| Id | Requirement | Code | Tests | Lot | Status |
|---|---|---|---|---|---|
| EF-01 | Declare a target application | `src/piege/types.py` (`Application`) | `tests/test_types.py` | 0 | done |
| EF-02 | Applicable techniques and planned coverage | — | — | 2, 3 | todo |
| EF-03 | Record a signed mandate | `src/piege/types.py` (`Mandat`) | `tests/test_types.py` | 0 | done |
| EF-04 | Refuse execution without a valid mandate | — | R1 | 3, 10 | todo |
| EF-05 | Refuse a technique outside the mandate scope | — | R4 | 10 | todo |
| EF-10 | Run a campaign (order, bounded parallelism) | — | — | 3 | todo |
| EF-11 | Targeted campaign on a declared change | — | — | 3 | todo |
| EF-12 | Call/token budget, clean stop at the threshold | — | R3 | 3 | todo |
| EF-13 | Reproducibility at a fixed seed | `src/piege/types_base.py` (`hash_stable`) | `tests/test_types.py` | 0, 3 | partial |
| EF-14 | Log every exchange | — | — | 3 | todo |
| EF-15 | Immediate suspension, state kept | — | R5 | 3 | todo |
| EF-16 | Multi-turn techniques with a bounded turn count | — | — | 4 | todo |
| EF-17 | Family F on an isolated test index | — | R7 | 7 | todo |
| EF-20 | Verdict: success / failure / ambiguous, structured | — | — | 5 | todo |
| EF-21 | Confidence and grounding citation per verdict | — | — | 5 | todo |
| EF-22 | Low-confidence verdicts to human review | — | — | 5 | todo |
| EF-23 | Severity never produced by a model | `src/piege/severite.py` | `tests/test_severite.py` | 0, 6 | done |
| EF-24 | Deduplicate findings | — | — | 5, 9 | todo |
| EF-30 | Load a legitimate-request corpus (≥ 50) | `src/piege/types.py` (`CorpusLegitime`) | `tests/test_types.py` | 0, 8 | partial |
| EF-31 | Run the corpus as a campaign, measure refusal rate | — | R9 | 8 | todo |
| EF-32 | Classify each refusal | — | R9 | 8 | todo |
| EF-33 | Estimate the loss of a false refusal | `src/piege/severite.py` (`perte`, `heures_perdues`) | `tests/test_severite.py` | 0, 8 | done |
| EF-34 | Refuse family G without a corpus, explicitly | `src/piege/erreurs.py` (`CorpusLegitimeAbsent`) | R8 | 8 | partial |
| EF-40 | At least one fix per finding | — | — | 9 | todo |
| EF-41 | Rank fixes by effort and risk reduction | — | — | 9 | todo |
| EF-42 | Apply a guardrail fix only after human approval | `src/piege/erreurs.py` (`AutorisationHumaineAbsente`) | R10, R11 | 9, 10 | partial |
| EF-43 | Replay the original attack, record the closure proof | — | R11 | 9 | todo |
| EF-44 | Detect a regression | — | — | 9 | todo |
| EF-45 | Detect a side effect on false refusals | — | R12 | 9 | todo |
| EF-50 | Campaign report | — | — | 12 | todo |
| EF-51 | Export in French and English, with citations | — | R15 | 12 | todo |
| EF-52 | Trend per application | — | — | 12, 13 | todo |
| EF-53 | Dated third-party attestation, poor in detail | — | R16 | 12 | todo |
| EF-54 | Full history, replay of one technique | — | R19 | 12 | todo |
| EF-60 | Strict tenant isolation | — | R14 | 10 | todo |
| EF-61 | Tenant identity from the token only | — | R14 | 10 | todo |
| EF-62 | Fleet view for the MSP analyst, tenant view for the customer | — | — | 12 | todo |
| EF-63 | Cost bounded and exposed per tenant | — | R17 | 11 | todo |

## Non-functional requirements (ENF-*)

| Id | Requirement | Code | Tests | Lot | Status |
|---|---|---|---|---|---|
| ENF-01 | No execution without a valid mandate | `src/piege/erreurs.py` | R1, R2 | 3, 10 | partial |
| ENF-02 | Call/token budget hard-capped in code | — | R3 | 3 | todo |
| ENF-03 | No availability attack | `catalogue/` (budgets, turns) | catalogue validator | 2 | todo |
| ENF-04 | Complete immutable logging | `src/piege/types_base.py` (`empreinte`) | `tests/test_types.py` | 0, 10 | partial |
| ENF-05 | Reproducibility at a fixed seed | `src/piege/types_base.py` (`hash_stable`) | `tests/test_types.py` | 0, 3 | partial |
| ENF-06 | Tenant isolation enforced by identity | — | R14 | 10 | todo |
| ENF-07 | No real personal data in the demo set | `demo/` | `tests/test_demo_corpus.py` | 1 | todo |
| ENF-08 | Configurable retention, proven purge | — | R20 | 10 | todo |
| ENF-09 | Full campaign < 30 min | — | — | 3 | todo |
| ENF-10 | Measured cost exposed | — | R17 | 11 | todo |
| ENF-11 | FR/EN interface, EN deliverables | `docs/` | — | 12, 16 | partial |
| ENF-12 | Files < 500 lines, functions < 50, CI ≤ 5 min | `scripts/gardes/tailles.py`, `.github/workflows/ci-budget.yml` | `tests/test_gardes.py` | 0 | done |
| ENF-13 | Reproducible IaC deployment | `iac/` | — | 14 | todo |
| ENF-14 | One-gesture emergency stop | — | R5 | 3, 12 | todo |
| ENF-15 | Stays online free of charge until 22 Jan 2027 | `iac/`, `docs/RUNBOOK.md` | — | 14 | todo |

## Indicators (KPI-*)

| Id | Indicator | Code | Tests | Lot | Status |
|---|---|---|---|---|---|
| KPI-1 | Bypass rate | — | — | 12 | todo |
| KPI-2 | Open critical findings | `src/piege/severite.py` | `tests/test_severite.py` | 0, 12 | partial |
| KPI-3 | Time to closure | — | — | 9, 12 | todo |
| KPI-4 | Time to cover a new technique | `catalogue/` (data-only) | R18 | 2, 3 | todo |
| KPI-5 | False refusals | `src/piege/severite.py` | `tests/test_severite.py` | 0, 8 | partial |
| KPI-6 | Catalogue coverage | — | — | 2, 12 | todo |
| KPI-7 | Measured cost per campaign | — | R17 | 11 | todo |
| KPI-8 | Reproducibility | `src/piege/types_base.py` | R13 | 0, 3 | partial |

## Transverse rules (CONTRACTS.md §1)

| Rule | Enforced by | Tests | Status |
|---|---|---|---|
| C1 sizes | `scripts/gardes/tailles.py` (CI) | `tests/test_gardes.py` | done |
| C2 CI ≤ 5 min | `.github/workflows/ci-budget.yml` | `check_timeouts.py` | done |
| C3 no third-party dependency | — | `tests/test_depots.py` | done |
| C4 offline tests | — | `tests/test_depots.py` | done |
| C5 no model-computed severity | `src/piege/severite.py` | `tests/test_severite.py` | done |
| C6 single clock | `src/piege/types_base.py` | `tests/test_depots.py` | done |
| C7 FR code / EN deliverables | review | — | ongoing |
| C8 disjoint file ownership | `couche0` check | — | ongoing |
| C9 reproducibility | `hash_stable`, seeds | R13 | partial |
| C10 no availability attack | catalogue budgets | catalogue validator | todo |
