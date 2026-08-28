resource "aws_kms_key" "quarantine" {
  description             = "Fincilia private pilot quarantine objects"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = { Name = "${local.name}-quarantine", DataZone = "quarantine" }
}

resource "aws_kms_alias" "quarantine" {
  name          = "alias/fincilia/private-pilot/quarantine"
  target_key_id = aws_kms_key.quarantine.key_id
}

resource "aws_kms_key" "evidence" {
  description             = "Fincilia private pilot raw derived and export evidence"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = { Name = "${local.name}-evidence", DataZone = "evidence" }
}

resource "aws_kms_alias" "evidence" {
  name          = "alias/fincilia/private-pilot/evidence"
  target_key_id = aws_kms_key.evidence.key_id
}

resource "aws_kms_key" "database" {
  description             = "Fincilia private pilot RDS Valkey and runtime secrets"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = { Name = "${local.name}-database", DataZone = "database" }
}

resource "aws_kms_alias" "database" {
  name          = "alias/fincilia/private-pilot/database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_kms_key" "audit" {
  description             = "Fincilia private pilot audit and logs"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountAdministration"
        Effect    = "Allow"
        Principal = { AWS = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "CloudTrailDataKeys"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = ["kms:GenerateDataKey*", "kms:DescribeKey"]
        Resource  = "*"
        Condition = {
          StringLike = {
            "kms:EncryptionContext:aws:cloudtrail:arn" = "arn:${data.aws_partition.current.partition}:cloudtrail:${var.region}:${data.aws_caller_identity.current.account_id}:trail/${local.name}"
          }
        }
      },
      {
        Sid       = "RegionalCloudWatchLogs"
        Effect    = "Allow"
        Principal = { Service = "logs.${var.region}.amazonaws.com" }
        Action    = ["kms:Encrypt*", "kms:Decrypt*", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
        Resource  = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = [
              "arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/fincilia/private-pilot/*",
              "arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/rds/instance/${local.name}/*",
              "arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:aws-waf-logs-fincilia-private-pilot*",
            ]
          }
        }
      }
    ]
  })
  tags = { Name = "${local.name}-audit", DataZone = "audit" }
}

resource "aws_kms_alias" "audit" {
  name          = "alias/fincilia/private-pilot/audit"
  target_key_id = aws_kms_key.audit.key_id
}

resource "aws_kms_key" "gate" {
  description              = "Verify DRG-00 and DRG-01 attestations; runtime cannot sign"
  key_usage                = "SIGN_VERIFY"
  customer_master_key_spec = "RSA_2048"
  enable_key_rotation      = false
  deletion_window_in_days  = 30
  tags                     = { Name = "${local.name}-gate", DataZone = "gate-attestations" }
}

resource "aws_kms_alias" "gate" {
  name          = "alias/fincilia/private-pilot/gates"
  target_key_id = aws_kms_key.gate.key_id
}
