# Runbook — deployment and operations

## Deploy

```bash
aws cloudformation deploy --stack-name piege \
  --template-file iac/cloudformation.yaml \
  --region eu-west-3 --capabilities CAPABILITY_IAM
```

The CloudFormation template provisions the control plane (DynamoDB mandates
table, versioned proof bucket, Lambda with Bedrock/DynamoDB/S3 permissions, HTTP
API). The Lambda handler is `piege.api.serveur.gestionnaire_lambda`; the core
has no third-party dependency, so the package is just the code.

## Offline / CI

`make ci` (guard + catalogue + tests) needs nothing else. `make demo` runs a
full campaign against the synthetic target.

## Emergency stop

One gesture: `POST /campagnes/{id}/suspendre` from the portal or the API. The
engine re-checks the flag between every probe, so the effect is immediate; the
campaign state is kept and resumable (`POST /campagnes/{id}/reprendre`).

## Cost control

Measured cost per campaign is exposed on `/budget` and in the report. A gap
above 25 % with the annex F projection triggers review R17.

## Retention and purge

`DELETE /tenants/{id}` (the local proof of purge is `R20`; the DynamoDB adapter
iterates the `par-tenant` index). Proofs are immutable and versioned in S3.

## Rollback

The stack is one unit: deleting it removes the demo control plane. Proofs live
in a separate versioned bucket, so a stack refresh never touches evidence.
