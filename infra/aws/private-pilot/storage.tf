locals {
  object_zones = toset(["quarantine", "raw", "derived", "exports"])
  object_kms_keys = {
    quarantine = aws_kms_key.quarantine.arn
    raw        = aws_kms_key.evidence.arn
    derived    = aws_kms_key.evidence.arn
    exports    = aws_kms_key.evidence.arn
  }
}

resource "aws_s3_bucket" "objects" {
  for_each = local.object_zones

  bucket        = "fincilia-${data.aws_caller_identity.current.account_id}-private-pilot-${each.key}"
  force_destroy = false
  tags          = { Name = "${local.name}-${each.key}", DataZone = each.key }
}

resource "aws_s3_bucket_ownership_controls" "objects" {
  for_each = local.object_zones

  bucket = aws_s3_bucket.objects[each.key].id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_public_access_block" "objects" {
  for_each = local.object_zones

  bucket                  = aws_s3_bucket.objects[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "objects" {
  for_each = local.object_zones

  bucket = aws_s3_bucket.objects[each.key].id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "objects" {
  for_each = local.object_zones

  bucket = aws_s3_bucket.objects[each.key].id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = local.object_kms_keys[each.key]
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "objects" {
  for_each = local.object_zones

  bucket = aws_s3_bucket.objects[each.key].id
  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

data "aws_iam_policy_document" "object_tls" {
  for_each = local.object_zones

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.objects[each.key].arn,
      "${aws_s3_bucket.objects[each.key].arn}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "objects" {
  for_each = local.object_zones

  bucket = aws_s3_bucket.objects[each.key].id
  policy = data.aws_iam_policy_document.object_tls[each.key].json
}

resource "aws_s3_bucket" "audit" {
  bucket        = "fincilia-${data.aws_caller_identity.current.account_id}-private-pilot-audit"
  force_destroy = false
  tags          = { Name = "${local.name}-audit", DataZone = "audit" }
}

resource "aws_s3_bucket_ownership_controls" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.audit.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    id     = "retain-audit"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "STANDARD_IA"
    }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

# Los access logs del Application Load Balancer solo admiten SSE-S3. Se separan
# de CloudTrail para no rebajar el cifrado KMS de la evidencia de auditoria.
resource "aws_s3_bucket" "alb_logs" {
  bucket        = "fincilia-${data.aws_caller_identity.current.account_id}-private-pilot-alb-logs"
  force_destroy = false
  tags          = { Name = "${local.name}-alb-logs", DataZone = "edge-logs" }
}

resource "aws_s3_bucket_ownership_controls" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket                  = aws_s3_bucket.alb_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  rule {
    id     = "archive-edge-logs"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}
