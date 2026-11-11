# Observability — what is measured, where, and how

**Everything is measured, nothing is estimated.** The cost of a campaign comes
from the tokens actually consumed (ENF-10, KPI-7); an estimate is only ever
used as a comparison baseline, never as a published figure.

## What is collected

| Module | Collects | Used by |
|---|---|---|
| `compteurs.py` | Calls, input/output tokens, cost, per-model breakdown — thread-safe | Engine (lot 3), report (lot 12) |
| `couts.py` | The single price table, cost per exchange, measured campaign cost, cost per tenant | Report, account manager view (EF-63) |
| `traces.py` | Structured traces with durations, JSON Lines export | Portal, Amazon Quick (lot 13), AgentCore Observability |
| `budget.py` | Remaining budget per campaign, gap against the annex F projection (R17) | Portal, API `/budget`, review process |
| `agentcore.py` | OTLP-shaped projection and CloudWatch publication (lazy `boto3`) | Deployment (lot 14) |

## The price table

One place, one truth (`couts.py`): `nova-lite` 0.06 / 0.24, `modele-fort`
3.00 / 15.00, `inferhub-flash` 0.00075 / 0.00375 dollars per million tokens
(input / output). An unknown model raises an error instead of falling back to a
guessed price — a wrong invoice is exactly what this service promises never to
produce.

## The 25 % rule (R17)

`ecart_projection` compares the measured cost with the projection of annex F
(3.35 $ mixed, 0.17 $ Nova Lite, 8.91 $ strong model). Beyond a 25 % gap, in
either direction, a review is required: an under-estimate is as suspicious as
an over-estimate.

## Offline by default

No network, no AWS account and no third-party package is needed: counters,
traces, costs and the JSON Lines export all run locally. Publishing to
CloudWatch requires `boto3` and credentials, and says so explicitly when they
are missing.
