locals {
  compose_content = templatefile("${path.module}/runtime/compose.yaml.tftpl", {
    api_image    = var.api_image
    web_image    = var.web_image
    worker_image = var.worker_image
    release_sha  = var.release_sha
  })

  bundle_files = {
    "compose.yaml"                 = local.compose_content
    "bootstrap.sql"                = file("${path.module}/runtime/bootstrap.sql")
    "up.sh"                        = file("${path.module}/runtime/up.sh")
    "fincilia-t1.service"          = file("${path.module}/runtime/fincilia-t1.service")
    "fincilia-t1-autostop.service" = file("${path.module}/runtime/fincilia-t1-autostop.service")
    "fincilia-t1-autostop.timer"   = file("${path.module}/runtime/fincilia-t1-autostop.timer")
  }

  manifest_content = join("", [for name in sort(keys(local.bundle_files)) :
    "${sha256(local.bundle_files[name])}  ${name}\n"
  ])
}

resource "aws_s3_object" "runtime" {
  for_each = merge(local.bundle_files, { "manifest.sha256" = local.manifest_content })

  bucket                 = data.terraform_remote_state.t0.outputs.object_bucket_name
  key                    = "${local.bundle_prefix}/${each.key}"
  content                = each.value
  content_type           = endswith(each.key, ".yaml") ? "application/yaml" : "text/plain"
  server_side_encryption = "AES256"
  metadata = {
    data-class  = "synthetic_only"
    release-sha = var.release_sha
  }

  depends_on = [terraform_data.account_guard]
}

data "aws_iam_policy_document" "runtime_bundle" {
  statement {
    sid       = "ListExactDeploymentPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${data.terraform_remote_state.t0.outputs.object_bucket_name}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.bundle_prefix}/*"]
    }
  }

  statement {
    sid       = "ReadExactDeploymentBundle"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${data.terraform_remote_state.t0.outputs.object_bucket_name}/${local.bundle_prefix}/*"]
  }
}

resource "aws_iam_role_policy" "runtime_bundle" {
  name   = "fincilia-t1-runtime-bundle"
  role   = data.terraform_remote_state.t0.outputs.runtime_instance_profile
  policy = data.aws_iam_policy_document.runtime_bundle.json
}
