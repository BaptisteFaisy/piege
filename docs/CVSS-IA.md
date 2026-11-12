# CVSS-IA — mapping a Piège finding to a CVSS v3.1 vector

Piège classifies AI-application findings with its own severity grid
(`src/piege/severite.py`, computed by code — never by a model). To make those
findings comparable with the rest of a security programme, each finding is also
translated into a **CVSS v3.1 base vector**, with a documented mapping and a
`PIEGE-1.0` extension tag.

This mapping is deterministic code (`src/piege/severite_risque.py`), not a
model output: two runs on the same finding produce the same vector and score.

## Metric mapping

| CVSS metric | Piège source | Rule |
|---|---|---|
| **AV** Attack Vector | `exposition` | 3 (public internet) → `N`; 1–2 (internal) → `A` |
| **AC** Attack Complexity | `exploitabilite` | ≥ 3 (single message / trivial) → `L`; else → `H` |
| **PR** Privileges Required | `exposition` | internal (≤ 2) → `L`; public → `N` |
| **UI** User Interaction | family | indirect injection / poisoning (needs an upload or a victim read) → `R`; else → `N` |
| **S** Scope | family | poisoning, indirect injection, perimeter crossing → `C` (changed); else → `U` |
| **C** Confidentiality | `impact` | 4 (personal data / secret) → `H`; 3 (internal disclosure) → `L`; ≤ 2 → `N` |
| **I** Integrity | family | poisoning → `H`; indirect injection → `L`; else → `N` |
| **A** Availability | — | **always `N`** — Piège never tests availability (ENF-03) |

## Why availability is always None

Piège is forbidden by design from attacking availability: no saturation, no
unbounded loop, no quota exhaustion. A finding therefore never has an
availability impact, and `A:N` is hard-coded. This is a deliberate ethical
constraint, not a measurement gap.

## The extension tag

The vector carries `extension: PIEGE-1.0` to signal that the Scope and
Integrity metrics are driven by AI-specific families (corpus poisoning,
indirect injection) that classic CVSS does not model natively. The base score
itself is pure CVSS v3.1 and is computed with the standard FIRST formula.

## Aggregate risk score

Beyond per-finding CVSS, `score_risque_application` produces a single 0–100
score per application (higher = worse), from the **open** findings weighted by
severity (Critical 40, High 20, Medium 8, Low 2, Undetermined 5), plus a debt
component (up to +10) that grows the longer a finding stays open. Grades:
A < 10, B < 25, C < 50, D < 75, F ≥ 75. It is reproducible campaign after
campaign, so a customer can watch the curve fall as fixes land.
