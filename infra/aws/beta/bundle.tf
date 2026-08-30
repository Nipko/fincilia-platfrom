locals {
  compose_content = templatefile("${path.module}/runtime/compose.yaml.tftpl", {
    api_image    = var.api_image
    web_image    = var.web_image
    worker_image = var.worker_image
    release_sha  = var.release_sha
  })
  caddy_content = templatefile("${path.module}/runtime/Caddyfile.tftpl", {
    beta_domain = var.beta_domain
  })
  deployment_env_content = <<-EOT
    FINCILIA_BACKUP_BUCKET=${data.terraform_remote_state.t0.outputs.object_bucket_name}
    FINCILIA_BACKUP_PREFIX=${local.backup_prefix}
    FINCILIA_RELEASE_SHA=${var.release_sha}
    FINCILIA_REGISTRY=${local.registry}
    FINCILIA_RUNTIME_PARAMETER=/fincilia/closed-beta/runtime-env-v1
  EOT

  bundle_files = {
    "compose.yaml"                        = local.compose_content
    "Caddyfile"                           = local.caddy_content
    "nginx.conf"                          = file("${path.module}/runtime/nginx.conf")
    "bootstrap.sh"                        = file("${path.module}/runtime/bootstrap.sh")
    "up.sh"                               = file("${path.module}/runtime/up.sh")
    "invite.sh"                           = file("${path.module}/runtime/invite.sh")
    "backup.sh"                           = file("${path.module}/runtime/backup.sh")
    "restore-check.sh"                    = file("${path.module}/runtime/restore-check.sh")
    "deploy-release.sh"                   = file("${path.module}/runtime/deploy-release.sh")
    "deployment.env"                      = local.deployment_env_content
    "fincilia-beta.service"               = file("${path.module}/runtime/fincilia-beta.service")
    "fincilia-beta-backup.service"        = file("${path.module}/runtime/fincilia-beta-backup.service")
    "fincilia-beta-backup.timer"          = file("${path.module}/runtime/fincilia-beta-backup.timer")
    "fincilia-beta-restore-check.service" = file("${path.module}/runtime/fincilia-beta-restore-check.service")
    "fincilia-beta-restore-check.timer"   = file("${path.module}/runtime/fincilia-beta-restore-check.timer")
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
