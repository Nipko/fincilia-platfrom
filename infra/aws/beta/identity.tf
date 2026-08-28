data "aws_iam_policy_document" "assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "beta" {
  name               = "fincilia-closed-beta"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_instance_profile" "beta" {
  name = "fincilia-closed-beta"
  role = aws_iam_role.beta.name
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.beta.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "beta" {
  statement {
    sid       = "ListExactBetaPrefixes"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${data.terraform_remote_state.t0.outputs.object_bucket_name}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "${local.bundle_prefix}/*",
        "${local.backup_prefix}/*",
        "restore-checks/beta/*",
      ]
    }
  }

  statement {
    sid       = "ReadExactReleaseBundle"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${data.terraform_remote_state.t0.outputs.object_bucket_name}/${local.bundle_prefix}/*"]
  }

  statement {
    sid    = "SyntheticBackupAndRestoreEvidence"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      "arn:aws:s3:::${data.terraform_remote_state.t0.outputs.object_bucket_name}/${local.backup_prefix}/*",
      "arn:aws:s3:::${data.terraform_remote_state.t0.outputs.object_bucket_name}/restore-checks/beta/*",
    ]
  }

  statement {
    sid       = "EcrAuthorization"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "RecoverExactRuntimeSecretBundle"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:PutParameter",
    ]
    resources = [
      "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/fincilia/closed-beta/runtime-env-v1",
    ]
  }

  statement {
    sid    = "PullPinnedApplicationImages"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [for repository_url in values(data.terraform_remote_state.t0.outputs.ecr_repository_urls) :
    "arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/${trimprefix(repository_url, "${local.registry}/")}"]
  }

  statement {
    sid       = "PublishBetaHealthMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["Fincilia/ClosedBeta"]
    }
  }
}

resource "aws_iam_role_policy" "beta" {
  name   = "fincilia-closed-beta-minimum"
  role   = aws_iam_role.beta.id
  policy = data.aws_iam_policy_document.beta.json
}
