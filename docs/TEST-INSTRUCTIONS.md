# Test instructions — judge guide

Piège runs entirely offline; no AWS account, no third-party package and no
network call is required for the demo.

## 1. Full test suite

```bash
git clone https://github.com/BaptisteFaisy/piege && cd piege
make ci                 # guards + catalogue + tests (standard library only)
python3 -m piege.catalogue.valideur catalogue --resume
```

`make ci` executes the eight-family catalogue validation, the size guards
(files < 500 lines, functions < 50), the no-third-party-dependency check and
the full offline test suite.

## 2. The three demo moments, offline

```bash
python3 -m pytest tests/test_demo_bout_en_bout.py -v
```

- **Salary-grid leak** : technique A1 returns the grid ("32 400 EUR brut").
- **Corpus poisoning** : family F drops a contradicting document into an
  isolated index; the assistant relays it, then returns to the reference once
  the index is destroyed.
- **Policy 403** : a technique outside the mandate is refused with no probe
  sent, and the refusal is journalled.

## 3. Campaign and report

```bash
make demo && make rapport
```

## 3bis. The real campaign, replayed — still free

```bash
make demo-reel      # replays a recorded campaign of a real model: 0 calls, 0 $
make rapport        # FR/EN report of that real campaign
```

The recorded campaign (`demo/reel/campagne-reelle.json`) was run against a
real model on 2026-11-12 (5 calls, 5 941 tokens, **0.00005 $** measured, one
confirmed finding). The replay reads the recording — no key, no account, no
network — so the judge sees real model outputs at zero cost. Full guide:
`docs/DEMO-GRATUITE.md`.

## 3ter. One live, free model response

```bash
make demo-libre    # a real model, called live, leaks the salary grid — free
```

The free provider (Pollinations, no key) answers in ~8 s. See
`docs/DEMO-GRATUITE.md` for the alternatives (Groq free, OpenRouter `:free`).

## 3quater. The whole dossier for the jury

```bash
make jury           # dossier-jury/ : campaign, reports, attestation, closure,
                    # 20 proven recipes, recalculated traceability, evaluation
```

## 4. Portal

```bash
python3 -m piege.api.serveur --port 8080
# open http://127.0.0.1:8080/ — declare, sign the mandate, run, fix, replay.
```

The portal token selector (`jeton:<tenant>:<role>`) is a **test-only** identity
convention documented in `docs/CONTRACTS-INTERFACES.md`; production identity is
AgentCore Identity, tenant derived from the token only.
