# Piège — continuous penetration testing for generative-AI applications

**Piège** ("trap") is the service an MSP sells on subscription: for every
generative-AI application a customer runs, an attacking agent probes it
continuously, measures what gets through, classifies each finding with a
severity **computed by code and never stated by a model**, proposes a fix,
applies it after explicit human approval, and **replays the attack to prove
the finding is closed**.

Two things set it apart from everything else on the market:

1. **RAG corpus poisoning is a first-class attack family.** Dropping a booby-
   trapped document into a knowledge source and checking whether the assistant
   relays it is the most realistic attack there is — it requires no technical
   access at all, only the right to upload a file.
2. **False refusals are measured as rigorously as leaks.** An assistant that
   refuses a perfectly legitimate request is a failure too. The customer report
   shows both numbers side by side: what leaks, and what is broken by excess
   caution.

Rules are enforced **by the gateway, not by the prompt**: scope, call budget,
production ban and emergency stop are decided by AgentCore Policy *before* a
tool runs. An attacking agent that tries to widen its own scope cannot.

> Submitted to the **AWS Agentic MSP Hackathon — Track 2** (Deliver AI-Driven
> Outcomes for Customers), targeting the *Best Amazon Bedrock Application*
> special prize. Design document: `docs/spec/cahier-des-charges.fr.md`
> (French, internal), high-level design: `docs/HLD.md`.

## Status

Under active development (S0 → S4, November–December 2026). The frozen
interface contracts live in `docs/CONTRACTS.md`,
`docs/CONTRACTS-INTERFACES.md` and `docs/CONTRACTS-LOTS.md`: every lot is a
branch, a pull request, and a disjoint set of files, merged by the Mergify
queue alone.

## Quick start (no AWS account, no third-party package)

```bash
git clone https://github.com/BaptisteFaisy/piege && cd piege
make ci          # guards + catalogue validation + tests (standard library only)
make demo        # full campaign against the intentionally vulnerable HR demo target
make rapport     # customer report, French and English
```

`make demo` runs entirely offline against the deterministic `local` provider
(a simulated Bedrock model, simulated Guardrails and a simulated knowledge
base), so the whole loop — probe, judge, severity, fix, replay, regression,
side-effect — is reproducible on a laptop and in CI.

Point it at real AWS services with the optional extras:

```bash
pip install -e '.[dev,aws,llm]'
export PIEGE_FOURNISSEUR=bedrock AWS_REGION=eu-west-3
python3 -m piege.cli demo --cible demo/cible/guichet-rh.yaml
```

## Layout

| Path | Contents |
|---|---|
| `src/piege/` | Engine: catalogue, campaign orchestrator, agents, severity, policy, storage, API, reports |
| `catalogue/` | The 60 attack techniques, one YAML data file each (no code needed to add one) |
| `demo/` | "Guichet RH" demo target, synthetic corpus, legitimate-request corpus |
| `eval/` | Evaluation harness: 20 vulnerable targets, 20 healthy targets, 100 labelled verdicts |
| `portal/` | Static customer portal (no build step) |
| `iac/` | Reproducible deployment (CloudFormation / CDK) and runbook |
| `docs/` | Contracts, HLD, architecture diagram, submission, test instructions |
| `tests/` | Mirrors `src/` — deterministic, offline, no network |

## AWS services

Amazon Bedrock (models, Guardrails, Knowledge Bases, Data Automation),
Bedrock AgentCore (Runtime, Gateway, Policy, Identity, Memory, Observability),
Strands Agents for the attacking agents, Amazon Quick for the fleet dashboard,
plus Step Functions, Lambda, DynamoDB, S3, Cognito, API Gateway and CloudFront
as infrastructure. See `docs/ARCHITECTURE.md`.

## Hard rules of the codebase

- A file is **under 500 lines**, a function **under 50 lines** (`scripts/gardes/tailles.py` enforces both in CI).
- CI answers in **5 minutes or less** (`ci-budget` check).
- **No severity is ever produced by a model** — `src/piege/severite.py` computes it from observed facts.
- **No campaign runs without a valid mandate** in its validity window (EF-04, ENF-01).
- **No attack targets availability**: no saturation, no volumetric denial of service (ENF-03).
- Mergify is the only merge driver; conflicts are resolved by the Hermes agent (InferHub).

## Legal and ethical frame

Testing a system without authorisation is an offence. Piège makes authorisation
a *technical precondition* of execution: nothing runs without a signed, dated,
scoped mandate, production is banned by the catalogue itself for the families
that must never touch it, and every probe and response is logged in a chained,
append-only journal. The demo dataset is 100 % synthetic and watermarked as
such. See chapter 21 of the design document.
