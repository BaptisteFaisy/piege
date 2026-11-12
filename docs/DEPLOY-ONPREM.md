# On-premises and self-hosted deployment

Piège's core has **no third-party dependency**: it runs offline on a laptop, in
a container, or behind a customer's firewall. Two paths are provided — Docker
for a self-hosted control plane, Terraform for the AWS-managed one.

## Docker (self-hosted, offline)

```bash
docker compose up --build      # API + portal on http://localhost:8080/
```

Or build and smoke-test in one step:

```bash
bash scripts/build-docker.sh
```

The image runs as a non-root user, exposes port 8080, and persists data in the
`piege-data` volume (mounted at `/data`). By default it uses the deterministic
`local` provider — no AWS account, no network, no model cost. Set
`PIEGE_FOURNISSEUR=bedrock` and provide AWS credentials to drive real Bedrock
models and Guardrails.

The same server process serves both the JSON API (`/api/...`) and the static
portal (`/`), so the portal's API calls work with no extra configuration.

## Terraform (AWS-managed control plane)

```bash
cd iac/terraform
zip -r piege-lambda.zip ../../src ../../pyproject.toml   # package the function
terraform init
terraform apply -var environnement=demo -var region=eu-west-3
```

The Terraform plan mirrors `iac/cloudformation.yaml`: DynamoDB mandates table
(with a per-tenant index), versioned S3 proof bucket, Lambda execution role
(DynamoDB, S3, Bedrock InvokeModel/Converse/ApplyGuardrail), the API function
(`piege.api.serveur.gestionnaire_lambda`), and an HTTP API Gateway v2 with a
default route. Outputs: API URL, table and bucket names, account id.

Region: `eu-west-3` by default, `eu-central-1` as a fallback (availability of
Guardrails and AgentCore is confirmed in S1 — design document, chapter 31).

## Verification

```bash
curl http://localhost:8080/api/health -H "Authorization: Bearer jeton:TEN-demo:analyste"
```

A `200` with `"statut": "ok"` confirms the control plane is up. The full
acceptance suite (`make ci`) runs the same offline, with no infrastructure.

## Notes

- The Lambda package is just the source tree: `pip install -e .` adds no
  dependency, so the deployment artifact is small and reproducible.
- Emergency stop, tenant isolation and the mandate precondition are enforced in
  code, identically offline and on AWS — there is no "cloud-only" security.
- Proofs are immutable and versioned; a stack refresh never touches evidence.
