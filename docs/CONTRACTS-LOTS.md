# CONTRACTS-LOTS — file ownership and pull-request discipline

Companion to `CONTRACTS.md` and `CONTRACTS-INTERFACES.md`. One lot = one
branch = one pull request = a **disjoint** set of files (spec §28).

## 1. Launch order

```
0 alone → {1, 2, 6} → {3, 10} → {4, 5, 7, 8, 11} → {9, 12, 15} → {13, 14} → {16, 17}
```

A lot may start as soon as the lots it depends on are **merged** (not opened).
While waiting, it may code against the frozen interfaces and keep its tests
green by stubbing nothing: the interfaces of lot 0 (`types`, `erreurs`) are
already on `main`.

## 2. Ownership map (exclusive)

| Lot | Owns (exclusive) | Depends on |
|---|---|---|
| **0** | `src/piege/types.py`, `src/piege/types_base.py`, `src/piege/types_enum.py`, `src/piege/erreurs.py`, `src/piege/severite.py` (reference implementation of the frozen rules), `src/piege/__init__.py`, `docs/CONTRACTS*.md`, `docs/TRACEABILITY.md`, `scripts/gardes/`, `scripts/lance_tests.py`, `.github/`, `.mergify.yml`, `pyproject.toml`, `Makefile`, `tests/test_types.py`, `tests/test_erreurs.py`, `tests/test_gardes.py`, `tests/test_depots.py` | — |
| **1** | `demo/`, `src/piege/cibles/`, `tests/test_cibles*.py`, `tests/test_demo_corpus.py` | 0 |
| **2** | `catalogue/`, `src/piege/catalogue/`, `tests/test_catalogue*.py`, `tests/test_chargeur_yaml.py` | 0 |
| **3** | `src/piege/moteur/`, `src/piege/fournisseurs/`, `src/piege/cli.py`, `tests/test_moteur*.py`, `tests/test_fournisseurs*.py`, `tests/test_reproductibilite.py`, `tests/test_cli.py` | 0, 2 |
| **4** | `src/piege/agents/attaquant/`, `tests/test_attaquant*.py` | 3 |
| **5** | `src/piege/agents/juge/`, `tests/test_juge*.py` (+ ajout de l'enregistrement `Verdict` à `src/piege/types.py`, autorisé par le lot 0) | 3 |
| **6** | `src/piege/severite_tableaux.py` (exploitability table for the 60 techniques, cross-checked against `severite.exploitabilite`), `tests/test_severite.py` (exhaustive), `tests/test_severite_tableaux.py` | 0, 2 |
| **7** | `src/piege/familles/empoisonnement/`, `tests/test_famille_f*.py` | 1, 3 |
| **8** | `src/piege/familles/faux_refus/`, `tests/test_famille_g*.py` | 1, 3 |
| **9** | `src/piege/correctifs/`, `tests/test_correctifs*.py` | 5, 6 |
| **10** | `src/piege/securite/`, `src/piege/stockage/`, `tests/test_securite*.py`, `tests/test_stockage*.py`, `tests/test_multi_tenant.py` | 0 |
| **11** | `src/piege/observabilite/`, `tests/test_observabilite*.py` | 3 |
| **12** | `src/piege/api/`, `src/piege/rapport/`, `portal/`, `tests/test_api*.py`, `tests/test_rapport*.py` | 5, 6, 9 |
| **13** | `infra/quick/`, `docs/QUICK.md` | 12 |
| **14** | `iac/`, `docs/RUNBOOK.md`, `scripts/deploie.sh` | 10, 12 |
| **15** | `eval/`, `tests/test_eval*.py` | 4, 5 |
| **16** | `docs/README-EN.md` (if needed), `docs/HLD.md`, `docs/ARCHITECTURE.md`, `docs/SUBMISSION.md`, `docs/TEST-INSTRUCTIONS.md`, `docs/LEGAL.md` | all |
| **17** | `media/`, `docs/VIDEO.md` | 12, 16 |

Shared, append-only files (a lot may **add** a row, never rewrite another
lot's row): `docs/TRACEABILITY.md`.

Nobody touches: `docs/fr/CAHIER-DES-CHARGES.md` (verbatim input),
`.github/workflows/pr-auto-merge.yml`, `.github/fireworks/` (proven pipeline,
owned by lot 0 infra).

## 3. Pull-request discipline

1. Branch name: `lot-<N>-<slug>` (e.g. `lot-06-severite`). A branch dies with
   its pull request: merged or closed → deleted on GitHub **and** locally,
   worktree removed.
2. Body must contain a `## Scope` section listing **every** changed path as a
   bullet, else `couche0` fails:

   ```markdown
   ## Scope
   - `src/piege/severite.py`
   - `tests/test_severite.py`
   - `docs/TRACEABILITY.md`
   ```

3. Required checks: `ci`, `ci-budget`, `couche0`. Mergify merges alone
   (rebase, linear history). Conflicts are resolved by the Hermes agent
   (InferHub); a human is asked only when the agent labels
   `intervention-humaine`.
4. Priority: `urgent` label for hotfixes and blocking PRs only,
   `priority-low` for documentation-only work.
5. Definition of done for a lot:
   - code + tests, all green in CI under 5 minutes;
   - every file < 500 lines, every function < 50 lines;
   - `docs/TRACEABILITY.md` rows added for each `EF-*` / `ENF-*` / `KPI-*` it covers;
   - no third-party import at module top level (C3);
   - tests offline and deterministic (C4, C9);
   - the acceptance rows it owns (spec §30.2, R1…R20) pass locally.

## 4. Acceptance map (spec §30.2)

| Test | Lot(s) |
|---|---|
| R1 no mandate → explicit refusal | 3, 10 |
| R2 expired mandate → refusal | 10 |
| R3 call budget exceeded → clean stop, state kept | 3 |
| R4 out-of-scope target → 403 from Policy, journalled | 10, 3 |
| R5 suspend a running campaign < 5 s, resumable | 3 |
| R6 family A on the demo target → A1 succeeds, Critique computed | 1, 2, 4, 5, 6 |
| R7 family F on the test index → relay detected, index destroyed | 7 |
| R8 family G without a corpus → explicit refusal | 8 |
| R9 family G with a corpus → classified false refusals, quantified loss | 8 |
| R10 fix without approval → refusal | 9, 10 |
| R11 fix with approval → applied, replayed, dated proof | 9 |
| R12 side effect → false refusals increase reported on the same line | 9, 8 |
| R13 two campaigns at the same seed → identical verdicts | 3 |
| R14 tenant A reads tenant B findings → refusal, journalled | 10, 12 |
| R15 report exported in English → complete, citations included | 12 |
| R16 third-party attestation → poor in detail | 12 |
| R17 measured cost → gap < 25 % with Annexe F | 11 |
| R18 add a technique → executable without a code change | 2, 3 |
| R19 replay a finding from the portal → identical replay | 12, 9 |
| R20 purge a tenant → data gone, proof of purge | 10 |

## 5. Rules reminded to every sub-agent

- Files < 500 lines, functions < 50 lines, CI ≤ 5 min.
- Never rewrite a file owned by another lot; never delegate further.
- After three failures on the same point: stop, leave the code as is, answer KO
  with the exact error and the files touched.
- No network in tests, no AWS credential required, no third-party import at
  module level.
- French identifiers and docstrings; English for every customer deliverable.
