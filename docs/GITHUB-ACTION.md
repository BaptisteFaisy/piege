# GitHub Action — Piège scan

Turn Piège into a CI gate: run a penetration-test campaign against an AI
application whenever its prompt, model or corpus changes, and report the
findings on the pull request.

The action lives at the repository root (`action.yml`) and runs the engine with
**no third-party dependency** (standard-library Python only).

## Two modes

1. **Offline** (default): scans a local target spec through the engine. No
   network, no AWS account, no cost. Ideal for a CI gate on a demo or test
   target.
2. **Remote**: when `api_url` is set, the action drives a running Piège API
   through the Python SDK (`src/piege/sdk.py`) and reports the live findings.

## Use it in a customer repository

Copy `.github/workflows/exemple-scan.yml` into the customer repo and trigger it
on the changes that matter:

```yaml
on:
  push:
    paths:
      - "prompts/**"
      - "model.json"
      - "corpus/**"
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
```

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `api_url` | _(empty)_ | Remote Piège API base URL; empty = offline scan |
| `tenant_token` | _(empty)_ | Identity token `jeton:<tenant>:<role>` (required with `api_url`) |
| `target` | `demo/cible/guichet-rh.json` | Target spec for the offline scan |
| `techniques` | _(all)_ | Comma-separated technique ids to run |
| `seed` | `0` | Reproducibility seed |
| `comment` | `false` | Post a summary comment on the pull request |

## Outputs

`findings`, `critiques`, `campagne_id` — usable by downstream steps (e.g. fail
the build when `critiques > 0`).

## Notes

- The example workflow in this repository is **`workflow_dispatch` only**: it
  never runs on this repo's pull requests, so it cannot interfere with the
  required checks.
- The token is a secret; it is passed through `env`, never echoed, never
  committed.
- Severity is computed by code, never by a model: the gate is deterministic and
  reproducible at a fixed seed.
