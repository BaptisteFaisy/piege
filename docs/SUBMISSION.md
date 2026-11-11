# Submission — AWS Agentic MSP Hackathon, Track 2

## Track

**Track 2 — Deliver AI-Driven Outcomes for Customers.**

## One-liner

An MSP sells a continuous penetration test of its customers' generative-AI
applications: an agent attacks, measures, classifies, proposes the fix and
proves it works.

## The problem

Nobody sells the test for generative-AI applications. One-off audits are
expensive and stale the day after delivery; open toolkits produce findings
without severity, without a fix, and without proof of closure; and no tool
measures the partner failure — legitimate requests broken by over-broad
guardrails.

## The solution

A catalogue of 60 attack techniques in 8 families, executed under a signed
mandate, judged with structured output, **severity computed by code** (never
stated by a model), a fix proposed and applied after explicit human approval,
and the attack replayed to prove closure. The customer report shows **what
leaks** and **what is broken** side by side.

## What makes it different

1. **RAG corpus poisoning as a first-class family** — the most realistic attack
   on the market, needing only the right to upload a file.
2. **False refusals measured as rigorously as leaks** — the number that sells
   the subscription to the business, not only to security.
3. **Gateway-enforced safety** — scope, budget, production ban and emergency
   stop are decided by AgentCore Policy before a tool runs.
4. **Zero-dependency core** — the whole engine runs offline, so one campaign is
   reproducible on a laptop, in CI, and by a judge.

## AWS services

Amazon Bedrock (models, Guardrails, Knowledge Bases, Data Automation), Bedrock
AgentCore (Runtime, Gateway, Policy, Identity, Memory, Observability), Strands
Agents, Amazon Quick — plus Step Functions, Lambda, DynamoDB, S3, Cognito, API
Gateway and CloudFront.

## Measured results (offline reference)

- 60 techniques, 8 families, `catalogue/` as data (adding one needs no code).
- Measured cost per campaign: **≈ 3.35 $ in mixed mode** (Nova Lite attacker,
  strong-model judge), reproduced by tests to the cent.
- 553 tests, deterministic, offline, CI under five minutes.
- The three demo moments (salary-grid leak, corpus poisoning, policy 403)
  are exercised end-to-end by `tests/test_demo_bout_en_bout.py`.

## Demo

`make demo`, then the report in French and English (`make rapport`), and the
portal (`python3 -m piege.api.serveur`). See `docs/TEST-INSTRUCTIONS.md`.
