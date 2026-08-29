output "foundation_only" {
  value = {
    deployment_authorized = false
    real_data_authorized  = false
    runtime_plane_enabled = var.runtime_plane_enabled
    desired_count         = var.service_desired_count
  }
}

output "required_dns_records" {
  value = {
    application = {
      name   = var.pilot_domain
      type   = "CNAME_or_ALIAS"
      target = try(aws_lb.pilot[0].dns_name, null)
    }
    certificate_validation = [for option in aws_acm_certificate.pilot.domain_validation_options : {
      name  = option.resource_record_name
      type  = option.resource_record_type
      value = option.resource_record_value
    }]
  }
}

output "cognito" {
  value = {
    user_pool_id      = aws_cognito_user_pool.pilot.id
    web_client_id     = aws_cognito_user_pool_client.web.id
    hosted_ui_domain  = local.oidc_base
    callback_uri      = "https://${var.pilot_domain}/api/auth/callback/cognito"
    google_configured = false
  }
}

output "runtime_secret_arns" {
  value = {
    application = aws_secretsmanager_secret.application.arn
    worker      = aws_secretsmanager_secret.worker.arn
    migrator    = aws_secretsmanager_secret.migrator.arn
    google      = aws_secretsmanager_secret.google.arn
  }
}

output "gate_key_arn" {
  value = aws_kms_key.gate.arn
}

output "object_buckets" {
  value = { for zone, bucket in aws_s3_bucket.objects : zone => bucket.id }
}

output "database" {
  value = {
    endpoint          = aws_db_instance.pilot.address
    port              = aws_db_instance.pilot.port
    master_secret_arn = try(aws_db_instance.pilot.master_user_secret[0].secret_arn, null)
  }
  sensitive = true
}
