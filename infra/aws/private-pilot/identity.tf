resource "aws_cognito_user_pool" "pilot" {
  name                     = local.name
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "ON"
  deletion_protection      = "ACTIVE"

  username_configuration {
    case_sensitive = false
  }

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 1
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${local.name}-web"
  user_pool_id = aws_cognito_user_pool.pilot.id

  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["https://${var.pilot_domain}/api/auth/callback/cognito"]
  logout_urls                          = ["https://${var.pilot_domain}/entrar"]
  supported_identity_providers         = ["COGNITO"]

  access_token_validity  = 15
  id_token_validity      = 15
  refresh_token_validity = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  enable_token_revocation       = true
  prevent_user_existence_errors = "ENABLED"

  # Google se configura fuera de IaC porque su client secret no puede entrar al
  # estado. La revision del provider es una evidencia DRG separada.
  lifecycle {
    ignore_changes  = [supported_identity_providers]
    prevent_destroy = true
  }
}

resource "aws_cognito_user_pool_domain" "pilot" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.pilot.id
}

resource "aws_secretsmanager_secret" "application" {
  name                    = "fincilia/private-pilot/application-runtime-v1"
  description             = "Valores runtime de API/web; se cargan fuera de OpenTofu"
  kms_key_id              = aws_kms_key.database.arn
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret" "worker" {
  name                    = "fincilia/private-pilot/worker-runtime-v1"
  description             = "Valores runtime del worker; se cargan fuera de OpenTofu"
  kms_key_id              = aws_kms_key.database.arn
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret" "migrator" {
  name                    = "fincilia/private-pilot/migrator-runtime-v1"
  description             = "Valores del job migrator; se cargan fuera de OpenTofu"
  kms_key_id              = aws_kms_key.database.arn
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret" "google" {
  name                    = "fincilia/private-pilot/google-oidc-v1"
  description             = "Client secret Google; provision manual sin estado IaC"
  kms_key_id              = aws_kms_key.database.arn
  recovery_window_in_days = 30
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role" "application" {
  name               = "${local.name}-application"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role" "worker" {
  name               = "${local.name}-worker"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role" "migrator" {
  name               = "${local.name}-migrator"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid       = "PullExactPilotRepositories"
    effect    = "Allow"
    actions   = ["ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = values(aws_ecr_repository.runtime)[*].arn
  }
  statement {
    sid       = "EcrAuthorization"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid       = "WriteExactLogGroups"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [for group in values(aws_cloudwatch_log_group.runtime) : "${group.arn}:*"]
  }
  statement {
    sid     = "ReadExactRuntimeSecrets"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.application.arn,
      aws_secretsmanager_secret.worker.arn,
      aws_secretsmanager_secret.migrator.arn,
    ]
  }
  statement {
    sid       = "DecryptRuntimeSecrets"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.database.arn]
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "${local.name}-execution-minimum"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

data "aws_iam_policy_document" "application" {
  statement {
    sid       = "ObjectZones"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = [for bucket in values(aws_s3_bucket.objects) : "${bucket.arn}/company/*"]
  }
  statement {
    sid       = "ListCompanyPrefixes"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = values(aws_s3_bucket.objects)[*].arn
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["company/*"]
    }
  }
  statement {
    sid       = "UseObjectKeys"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [aws_kms_key.quarantine.arn, aws_kms_key.evidence.arn]
  }
  statement {
    sid       = "EcsExecChannels"
    effect    = "Allow"
    actions   = ["ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel", "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel"]
    resources = ["*"]
  }
  statement {
    sid       = "VerifyGateAttestations"
    effect    = "Allow"
    actions   = ["kms:Verify", "kms:GetPublicKey", "kms:DescribeKey"]
    resources = [aws_kms_key.gate.arn]
  }
}

resource "aws_iam_role_policy" "application" {
  name   = "${local.name}-application-minimum"
  role   = aws_iam_role.application.id
  policy = data.aws_iam_policy_document.application.json
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid     = "ProcessingZones"
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:PutObject"]
    resources = [
      "${aws_s3_bucket.objects["quarantine"].arn}/company/*",
      "${aws_s3_bucket.objects["raw"].arn}/company/*",
      "${aws_s3_bucket.objects["derived"].arn}/company/*",
    ]
  }
  statement {
    sid       = "UseProcessingKeys"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [aws_kms_key.quarantine.arn, aws_kms_key.evidence.arn]
  }
  statement {
    sid       = "EcsExecChannels"
    effect    = "Allow"
    actions   = ["ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel", "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel"]
    resources = ["*"]
  }
  statement {
    sid       = "VerifyGateAttestations"
    effect    = "Allow"
    actions   = ["kms:Verify", "kms:GetPublicKey", "kms:DescribeKey"]
    resources = [aws_kms_key.gate.arn]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "${local.name}-worker-minimum"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

data "aws_iam_policy_document" "migrator" {
  statement {
    sid       = "EcsExecChannels"
    effect    = "Allow"
    actions   = ["ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel", "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "migrator" {
  name   = "${local.name}-migrator-minimum"
  role   = aws_iam_role.migrator.id
  policy = data.aws_iam_policy_document.migrator.json
}
