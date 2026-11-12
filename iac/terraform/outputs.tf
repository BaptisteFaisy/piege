# Piège — sorties du plan de contrôle.
output "url_api" {
  description = "Adresse de l'API Piège."
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "table_mandats" {
  description = "Nom de la table DynamoDB des mandats."
  value       = aws_dynamodb_table.mandats.name
}

output "bucket_preuves" {
  description = "Bucket S3 des preuves immuables."
  value       = aws_s3_bucket.preuves.bucket
}

output "compte" {
  description = "Identifiant du compte AWS déployé."
  value       = data.aws_caller_identity.actuel.account_id
}
