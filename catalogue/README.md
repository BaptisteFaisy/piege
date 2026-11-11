# Attack catalogue — 60 techniques, 8 families

The catalogue is **data, not code**: adding a technique means adding a YAML
entry, never changing the engine (spec §18.4, KPI-4, acceptance R18).

| Family | File | Techniques | What it attacks |
|---|---|---|---|
| A | `famille-a-injection-directe.yaml` | A1–A9 | The instruction is in the user message |
| B | `famille-b-injection-indirecte.yaml` | B1–B10 | The instruction is in what the app reads |
| C | `famille-c-extraction.yaml` | C1–C8 | Everything inside the context window |
| D | `famille-d-perimetre.yaml` | D1–D7 | Reaching what is not authorised |
| E | `famille-e-garde-fous.yaml` | E1–E6 | The guardrails themselves |
| F | `famille-f-empoisonnement-corpus.yaml` | F1–F8 | The RAG corpus (document dropped by an authorised person) |
| G | `famille-g-faux-refus.yaml` | G1–G7 | Legitimate requests wrongly refused |
| H | `famille-h-abus-fonctionnel.yaml` | H1–H5 | Using the assistant off-purpose |

Totals, verified by `python3 -m piege.catalogue.valideur catalogue`:

- 60 techniques, unique identifiers, one file per family;
- 311 tool calls for a full campaign, of which 175 outside production and 136
  for techniques that can **never** run in production;
- every family F technique requires the `depot_document_autorise` precondition
  and points at a template in `gabarits/`;
- every family G technique measures `refus` first and requires a legitimate
  request corpus supplied by the customer.

`production: jamais` is written in the data, not in a configuration file: no
mandate can lift it.

## Adding a technique

1. Add an entry to the right family file (schema in `LISEZ-MOI.md`).
2. If it belongs to family F, add its document template under `gabarits/`.
3. Run `python3 -m piege.catalogue.valideur catalogue --resume`.
4. Add the acceptance row in `docs/TRACEABILITY.md`.

No deployment, no code change: the next campaign picks it up.

## Legal note

These probes are security-test payloads intended for systems covered by a
signed mandate, on demonstration or pre-production targets. The demo corpus is
100 % synthetic and watermarked. Nothing here targets availability: no
saturation, no volumetric denial of service (ENF-03).
