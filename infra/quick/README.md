# Amazon Quick — fleet dashboard and trends

Quick is the spread of the customer-facing numbers to the **account manager**
and the **security officer**, from the data already measured by the engine.

## Datasets (exported by the API, `GET /budget` and `GET /tendances`)

- `tendances` : one row per campaign — date, techniques run, techniques
  successful, bypass rate, false refusals, measured cost, calls, tokens.
- `budget` : one row per tenant — measured total cost, campaigns, projection
  gap (annex F).

## Suggested sheets

1. **Bypass rate over time** (line) : is the customer getting safer, campaign
   after campaign?
2. **What is broken** (bars) : false refusals by criticality — the business
   impact of over-broad guardrails.
3. **Measured cost** (sparkline) : per tenant, against the 200 $ credit budget.

The definitions are code-driven and documented; no model ever writes a number
into a spreadsheet (same rule as the severity engine).
