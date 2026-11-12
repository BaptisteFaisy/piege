# Piège — plan de contrôle MSP : miroir Terraform de iac/cloudformation.yaml.
# Aucune étape manuelle non documentée (ENF-13). Le cœur étant sans dépendance
# tierce, la Lambda embarque le paquet tel quel.

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "actuel" {}

# --- Stockage : mandats, campagnes, découvertes (modèle de données §19) ---
resource "aws_dynamodb_table" "mandats" {
  name         = "${var.prefixe}-mandats"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "tenant_id"
    type = "S"
  }
  global_secondary_index {
    name            = "par-tenant"
    hash_key        = "tenant_id"
    projection_type = "ALL"
  }
}

# --- Preuves immuables et versionnées (ENF-04) ---
resource "aws_s3_bucket" "preuves" {
  bucket = "${var.prefixe}-preuves-${var.environnement}"
}

resource "aws_s3_bucket_versioning" "preuves" {
  bucket = aws_s3_bucket.preuves.id
  versioning_configuration {
    status = "Enabled"
  }
}

# --- Rôle d'exécution de la Lambda ---
resource "aws_iam_role" "api" {
  name = "${var.prefixe}-api-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "api" {
  name = "${var.prefixe}-api-policy"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query",
                    "dynamodb:Scan", "dynamodb:DeleteItem"]
        Resource = [aws_dynamodb_table.mandats.arn,
                    "${aws_dynamodb_table.mandats.arn}/index/par-tenant"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = "${aws_s3_bucket.preuves.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:Converse",
                    "bedrock:ApplyGuardrail"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream",
                    "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}

# --- Fonction API (cœur sans dépendance : le paquet est le code tel quel) ---
resource "aws_lambda_function" "api" {
  function_name = "${var.prefixe}-api"
  role          = aws_iam_role.api.arn
  runtime       = "python3.13"
  handler       = "piege.api.serveur.gestionnaire_lambda"
  memory_size   = 512
  timeout       = 60
  filename      = "${path.module}/piege-lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/piege-lambda.zip")

  environment {
    variables = {
      PIEGE_DONNEES     = "/tmp/donnees"
      PIEGE_FOURNISSEUR = "bedrock"
      PIEGE_MODELE      = var.modele_juge
    }
  }
}

# --- API HTTP (Gateway v2) ---
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.prefixe}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_stage" "defaut" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
