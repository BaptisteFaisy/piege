#!/usr/bin/env bash
# deploy.sh — déploiement reproductible du plan de contrôle (CloudFormation).
# Aucune étape manuelle non documentée (ENF-13). Exigences : aws cli, compte MSP,
# région eu-west-3 (sinon modifier --region).
set -euo pipefail

PILE="${1:-piege}"
REGION="${AWS_REGION:-eu-west-3}"
ENVIRONNEMENT="${PIEGE_ENVIRONNEMENT:-demo}"
STOCKAGE="${PIEGE_STOCKAGE:-piege}"

echo "==> Déploiement de la pile ${PILE} (${ENVIRONNEMENT}, ${REGION})"
aws cloudformation deploy \
  --region "${REGION}" \
  --stack-name "${PILE}" \
  --template-file iac/cloudformation.yaml \
  --parameter-overrides Environnement="${ENVIRONNEMENT}" EtatDeStockage="${STOCKAGE}" \
  --capabilities CAPABILITY_IAM

echo "==> Packaging de la Lambda (paquet stdlib, aucune dépendance)"
tarball="/tmp/piege-lambda.tar.gz"
tar -czf "${tarball}" pyproject.toml src/
aws lambda update-function-code \
  --region "${REGION}" \
  --function-name "${STOCKAGE}-api" \
  --zip-file "fileb://${tarball}"

echo "==> Adresse de l'API"
aws cloudformation describe-stacks --stack-name "${PILE}" --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='UrlApi'].OutputValue" --output text
echo "Déployé. Runbook : docs/RUNBOOK.md"
