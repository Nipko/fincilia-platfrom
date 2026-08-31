locals {
  github_oidc_subject = "repo:Nipko@16093741/fincilia-platfrom@1342497632:environment:private-pilot"
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  tags = {
    Name = "fincilia-private-pilot-github-oidc"
  }

  lifecycle {
    prevent_destroy = true
  }
}

data "aws_iam_policy_document" "github_actions_assume" {
  statement {
    sid     = "ExactImmutableRepositoryEnvironment"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_oidc_subject]
    }
  }
}

resource "aws_iam_role" "github_ecr_publisher" {
  name                 = "fincilia-private-pilot-ecr-publisher"
  description          = "Sesion OIDC temporal para publicar tres imagenes inmutables de Fincilia"
  assume_role_policy   = data.aws_iam_policy_document.github_actions_assume.json
  max_session_duration = 3600

  tags = {
    Name = "fincilia-private-pilot-ecr-publisher"
  }

  lifecycle {
    prevent_destroy = true
  }
}

data "aws_iam_policy_document" "github_ecr_publish" {
  statement {
    sid       = "AcquireEcrAuthorizationToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PublishAndInspectExactPilotRepositories"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeImageScanFindings",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [for repository in values(aws_ecr_repository.runtime) : repository.arn]
  }
}

resource "aws_iam_role_policy" "github_ecr_publisher" {
  name   = "publish-exact-private-pilot-images"
  role   = aws_iam_role.github_ecr_publisher.id
  policy = data.aws_iam_policy_document.github_ecr_publish.json

  lifecycle {
    prevent_destroy = true
  }
}
