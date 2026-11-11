# Architecture — Piège

```mermaid
flowchart TB
  subgraph CLIENT["Customer AWS account"]
    APP["Target application<br/>RAG assistant / agent"]
    KB["Knowledge Bases<br/>document corpus"]
    LOGS["Usage logs"]
  end

  subgraph MSP["MSP account — control plane"]
    PORTAL["Portal<br/>CloudFront + S3 + Cognito"]
    API["API<br/>API Gateway + Lambda"]
    SF["Step Functions"]
    DB["DynamoDB<br/>mandates · campaigns · findings"]
    S3["S3<br/>proofs · reports"]
    QUICK["Amazon Quick<br/>fleet &amp; trends"]
  end

  subgraph AGENT["AgentCore — data plane"]
    RT["Runtime<br/>isolated attacker sessions"]
    GW["Gateway<br/>controlled tool access"]
    POL["Policy<br/>scope · budget · stop"]
    ID["Identity<br/>tenant from token"]
    MEM["Memory"]
    OBS["Observability<br/>traces · cost"]
    JUDGE["Judge<br/>Bedrock, structured output"]
    IDX["Test index<br/>family F"]
  end

  PORTAL --> API
  API --> DB
  API --> SF
  SF --> POL
  POL --> RT
  RT --> GW --> APP
  RT --> IDX --> KB
  RT --> JUDGE
  RT --> OBS --> MEM
  API --> S3
  QUICK --> DB
```

The principle, borrowed from the rest of the portfolio: **rules are enforced by
the gateway, not by the prompt**. The local Python implementation of the policy
(`src/piege/securite/politique.py`) is the reference; the AgentCore adapter
projects it and verifies that the remote decision matches the local one.

The full literary specification is in `docs/fr/CAHIER-DES-CHARGES.md` (French).
The frozen interface contracts are `docs/CONTRACTS.md`,
`docs/CONTRACTS-INTERFACES.md` and `docs/CONTRACTS-LOTS.md`. The traceability
matrix (`docs/TRACEABILITY.md`) maps every requirement to code and tests.
