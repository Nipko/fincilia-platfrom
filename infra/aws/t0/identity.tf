data "aws_iam_policy_document" "runtime_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name               = "fincilia-t0-runtime"
  assume_role_policy = data.aws_iam_policy_document.runtime_assume.json
}

resource "aws_iam_instance_profile" "runtime" {
  name = "fincilia-t0-runtime"
  role = aws_iam_role.runtime.name
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.runtime.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "runtime" {
  statement {
    sid       = "ListSyntheticPrefixes"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.objects.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*", "quarantine/*", "derived/*"]
    }
  }

  statement {
    sid       = "SyntheticObjectAccess"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.objects.arn}/raw/*", "${aws_s3_bucket.objects.arn}/quarantine/*", "${aws_s3_bucket.objects.arn}/derived/*"]
  }

  statement {
    sid       = "EcrAuthorization"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PullPinnedImages"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer"
    ]
    resources = [for repository in aws_ecr_repository.runtime : repository.arn]
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "fincilia-t0-runtime-minimum"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.runtime.json
}
