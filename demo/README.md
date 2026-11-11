# Demo dataset — 100 % synthetic, watermarked

Nothing in this directory is real data. Every name is invented, every amount is
made up, and every file carries the watermark `SYNTHETIQUE — DEMONSTRATION`
(requirement ENF-07).

## The target

`cible/guichet-rh.json` describes "Guichet RH — cible de démonstration,
vulnérabilités intentionnelles": an HR assistant answering questions about
leave, health insurance and expenses. It is **deliberately naive**: no
separation between data and instructions, no guardrail. Naming it that way is
what makes the demo honest — a judge knows that a real application is not
attacked in three minutes.

`cible/guichet-rh-sain.json` is the same target with guardrails enabled. It is
used to measure the engine's false positives and to show the effect of the
proposed fixes.

## The corpus (`corpus/`)

| Folder | Files | Role |
|---|---|---|
| `legitime/` | 30 | Leave, health insurance, expenses, remote work, onboarding |
| `confidentiel/` | 3 | Documents that should never have been indexed: salary grid, interview report, termination procedure |
| `officiel/` | 1 | Reference procedure (work-accident declaration) — the authority that family F tries to contradict |
| `pieges/` | 6 | Templates dropped by the campaign into an **isolated test index** (family F) |

The `pieges/` folder is **not** indexed by the target: those files are the
ammunition of family F, deposited into a test index created and destroyed by
the campaign (EF-17).

## The legitimate-request corpus (`corpus-legitime/demandes.json`)

50 realistic employee requests with their declared business criticality, exactly
as annex E.3 requires:

| Criticality | Examples | Count |
|---|---|---|
| 4 | Work-accident declaration, harassment report, sick leave | 9 |
| 3 | Maternity/paternity leave, health insurance, health-cost reimbursement | 12 |
| 2 | Paid leave, remote work, expense claims | 18 |
| 1 | Canteen hours, site access | 11 |

Without this corpus, family G is **not executable**: the engine says so
explicitly instead of publishing an empty figure (EF-34).
