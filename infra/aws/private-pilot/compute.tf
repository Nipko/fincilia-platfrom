locals {
  repositories = toset(["api", "web", "worker"])
  oidc_issuer  = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.pilot.id}"
  oidc_base    = "https://${aws_cognito_user_pool_domain.pilot.domain}.auth.${var.region}.amazoncognito.com"
  cache_host   = try(aws_elasticache_replication_group.pilot[0].primary_endpoint_address, "disabled.invalid")

  api_environment = [
    { name = "FINCILIA_ENV", value = "pilot" },
    { name = "FINCILIA_SERVICE_NAME", value = "fincilia-api" },
    { name = "FINCILIA_LOG_LEVEL", value = "info" },
    { name = "FINCILIA_BUILD_REVISION", value = var.release_sha },
    { name = "FINCILIA_RELEASE_ID", value = "fnc-private-pilot-${substr(var.release_sha, 0, 12)}" },
    { name = "FINCILIA_OTEL_ENDPOINT", value = "disabled" },
    { name = "FINCILIA_SECRET_SOURCE", value = "aws_secrets_manager" },
    { name = "FINCILIA_DATABASE_POOL_MIN", value = "1" },
    { name = "FINCILIA_DATABASE_POOL_MAX", value = "6" },
    { name = "FINCILIA_DATABASE_STATEMENT_TIMEOUT_MS", value = "15000" },
    { name = "FINCILIA_CACHE_URL", value = "rediss://${local.cache_host}:6379/0" },
    { name = "FINCILIA_OBJECT_STORE_ENDPOINT", value = "https://s3.${var.region}.amazonaws.com" },
    { name = "FINCILIA_OBJECT_REGION", value = var.region },
    { name = "FINCILIA_OBJECT_CREDENTIALS_SOURCE", value = "aws_workload_identity" },
    { name = "FINCILIA_OBJECT_BUCKET_QUARANTINE", value = aws_s3_bucket.objects["quarantine"].id },
    { name = "FINCILIA_OBJECT_BUCKET_RAW", value = aws_s3_bucket.objects["raw"].id },
    { name = "FINCILIA_OBJECT_BUCKET_DERIVED", value = aws_s3_bucket.objects["derived"].id },
    { name = "FINCILIA_OBJECT_BUCKET_EXPORTS", value = aws_s3_bucket.objects["exports"].id },
    { name = "FINCILIA_AUTH_ISSUER", value = "https://${var.pilot_domain}" },
    { name = "FINCILIA_AUTH_AUDIENCE", value = "fincilia-api" },
    { name = "FINCILIA_AUTH_TOKEN_TTL_SECONDS", value = "900" },
    { name = "FINCILIA_IDENTIFIER_KEY_VERSION", value = "1" },
    { name = "FINCILIA_REAL_DATA_ENABLED", value = "false" },
    { name = "FINCILIA_AI_GATEWAY_ENABLED", value = "false" },
    { name = "FINCILIA_PAYMENTS_ENABLED", value = "false" },
    { name = "FINCILIA_REGISTRATION_INVITE_REQUIRED", value = "true" },
    { name = "FINCILIA_OIDC_ENABLED", value = "true" },
    { name = "FINCILIA_OIDC_ISSUER", value = local.oidc_issuer },
    { name = "FINCILIA_OIDC_CLIENT_ID", value = aws_cognito_user_pool_client.web.id },
    { name = "FINCILIA_OIDC_TOKEN_ENDPOINT", value = "${local.oidc_base}/oauth2/token" },
    { name = "FINCILIA_OIDC_USERINFO_ENDPOINT", value = "${local.oidc_base}/oauth2/userInfo" },
    { name = "FINCILIA_OIDC_REDIRECT_URI", value = "https://${var.pilot_domain}/api/auth/callback/cognito" },
    { name = "FINCILIA_IDENTITY_GATE_KMS_KEY_ID", value = aws_kms_key.gate.arn },
    { name = "FINCILIA_DATA_GATE_KMS_KEY_ID", value = aws_kms_key.gate.arn },
  ]

  api_secrets = [for name in [
    "FINCILIA_DATABASE_URL",
    "FINCILIA_AUTH_SIGNING_KEY",
    "FINCILIA_AUTHORIZATION_CONTEXT_HMAC_KEY",
    "FINCILIA_IDENTIFIER_TOKENIZATION_KEY",
    "FINCILIA_IDENTITY_BINDING_HMAC_KEY",
    "FINCILIA_IDENTITY_GATE_ATTESTATION",
    "FINCILIA_IDENTITY_GATE_SIGNATURE",
    "FINCILIA_DATA_GATE_ATTESTATION",
    "FINCILIA_DATA_GATE_SIGNATURE",
    ] : {
    name      = name
    valueFrom = "${aws_secretsmanager_secret.application.arn}:${name}::"
  }]

  web_environment = [
    { name = "FINCILIA_ENV", value = "pilot" },
    { name = "FINCILIA_API_BASE_URL", value = "http://127.0.0.1:8000" },
    { name = "FINCILIA_WEB_SECURE_COOKIES", value = "true" },
    { name = "FINCILIA_PUBLIC_STAGE", value = "private_pilot" },
    { name = "FINCILIA_PUBLIC_ORIGIN", value = "https://${var.pilot_domain}" },
    { name = "FINCILIA_REGISTRATION_INVITE_REQUIRED", value = "true" },
    { name = "FINCILIA_OIDC_ENABLED", value = "true" },
    { name = "FINCILIA_OIDC_AUTHORIZE_ENDPOINT", value = "${local.oidc_base}/oauth2/authorize" },
    { name = "FINCILIA_OIDC_REDIRECT_URI", value = "https://${var.pilot_domain}/api/auth/callback/cognito" },
    { name = "FINCILIA_OIDC_CLIENT_ID", value = aws_cognito_user_pool_client.web.id },
    { name = "NEXT_TELEMETRY_DISABLED", value = "1" },
  ]

  web_secrets = [{
    name      = "FINCILIA_OAUTH_TRANSACTION_KEY"
    valueFrom = "${aws_secretsmanager_secret.application.arn}:FINCILIA_OAUTH_TRANSACTION_KEY::"
  }]

  worker_environment = [
    { name = "FINCILIA_ENV", value = "pilot" },
    { name = "FINCILIA_SERVICE_NAME", value = "fincilia-worker" },
    { name = "FINCILIA_LOG_LEVEL", value = "info" },
    { name = "FINCILIA_BUILD_REVISION", value = var.release_sha },
    { name = "FINCILIA_RELEASE_ID", value = "fnc-private-pilot-${substr(var.release_sha, 0, 12)}" },
    { name = "FINCILIA_OTEL_ENDPOINT", value = "disabled" },
    { name = "FINCILIA_SECRET_SOURCE", value = "aws_secrets_manager" },
    { name = "FINCILIA_DATABASE_POOL_MIN", value = "1" },
    { name = "FINCILIA_DATABASE_POOL_MAX", value = "3" },
    { name = "FINCILIA_DATABASE_STATEMENT_TIMEOUT_MS", value = "30000" },
    { name = "FINCILIA_CACHE_URL", value = "rediss://${local.cache_host}:6379/1" },
    { name = "FINCILIA_OBJECT_STORE_ENDPOINT", value = "https://s3.${var.region}.amazonaws.com" },
    { name = "FINCILIA_OBJECT_REGION", value = var.region },
    { name = "FINCILIA_OBJECT_CREDENTIALS_SOURCE", value = "aws_workload_identity" },
    { name = "FINCILIA_OBJECT_BUCKET_QUARANTINE", value = aws_s3_bucket.objects["quarantine"].id },
    { name = "FINCILIA_OBJECT_BUCKET_RAW", value = aws_s3_bucket.objects["raw"].id },
    { name = "FINCILIA_OBJECT_BUCKET_DERIVED", value = aws_s3_bucket.objects["derived"].id },
    { name = "FINCILIA_OBJECT_BUCKET_EXPORTS", value = aws_s3_bucket.objects["exports"].id },
    { name = "FINCILIA_REAL_DATA_ENABLED", value = "false" },
    { name = "FINCILIA_AI_GATEWAY_ENABLED", value = "false" },
    { name = "FINCILIA_DATA_GATE_KMS_KEY_ID", value = aws_kms_key.gate.arn },
  ]
}

resource "aws_ecr_repository" "runtime" {
  for_each = local.repositories

  name                 = "fincilia/private-pilot/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.evidence.arn
  }
}

resource "aws_ecr_lifecycle_policy" "runtime" {
  for_each = local.repositories

  repository = aws_ecr_repository.runtime[each.key].name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain 30 immutable releases"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "runtime" {
  for_each = toset(["application", "worker", "migrator"])

  name              = "/fincilia/private-pilot/${each.key}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.audit.arn
}

resource "aws_ecs_cluster" "pilot" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enhanced"
  }
}

resource "aws_ecs_cluster_capacity_providers" "pilot" {
  cluster_name       = aws_ecs_cluster.pilot.name
  capacity_providers = ["FARGATE"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

resource "aws_ecs_task_definition" "application" {
  count = var.runtime_plane_enabled ? 1 : 0

  family                   = "${local.name}-application"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.application.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name                   = "api"
      image                  = var.api_image
      essential              = true
      readonlyRootFilesystem = true
      user                   = "10002"
      environment            = local.api_environment
      secrets                = local.api_secrets
      portMappings           = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)\""]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
      linuxParameters = { initProcessEnabled = true }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.runtime["application"].name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api"
        }
      }
    },
    {
      name                   = "web"
      image                  = var.web_image
      essential              = true
      readonlyRootFilesystem = true
      user                   = "10002"
      environment            = local.web_environment
      secrets                = local.web_secrets
      portMappings           = [{ containerPort = 3000, hostPort = 3000, protocol = "tcp" }]
      dependsOn              = [{ containerName = "api", condition = "HEALTHY" }]
      healthCheck = {
        command     = ["CMD-SHELL", "node -e \"require('http').get('http://127.0.0.1:3000/entrar',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))\""]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
      linuxParameters = { initProcessEnabled = true }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.runtime["application"].name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "web"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  count = var.runtime_plane_enabled ? 1 : 0

  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name                   = "worker"
    image                  = var.worker_image
    essential              = true
    readonlyRootFilesystem = true
    user                   = "10002"
    environment            = local.worker_environment
    secrets = [for name in [
      "FINCILIA_DATABASE_URL",
      "FINCILIA_DATA_GATE_ATTESTATION",
      "FINCILIA_DATA_GATE_SIGNATURE",
      ] : {
      name      = name
      valueFrom = "${aws_secretsmanager_secret.worker.arn}:${name}::"
    }]
    healthCheck = {
      command     = ["CMD-SHELL", "test -f /tmp/fincilia-worker-alive && find /tmp/fincilia-worker-alive -mmin -1 | grep -q ."]
      interval    = 15
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
    linuxParameters = { initProcessEnabled = true }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.runtime["worker"].name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "migrator" {
  count = var.runtime_plane_enabled ? 1 : 0

  family                   = "${local.name}-migrator"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.migrator.arn

  container_definitions = jsonencode([{
    name                   = "migrator"
    image                  = var.api_image
    essential              = true
    readonlyRootFilesystem = true
    user                   = "10002"
    entryPoint             = ["sh", "-c"]
    command                = ["exec python -m db.migrate.apply --dsn \"$${FINCILIA_MIGRATOR_URL}\""]
    environment = [
      { name = "FINCILIA_ENV", value = "pilot" },
      { name = "FINCILIA_SECRET_SOURCE", value = "aws_secrets_manager" },
      { name = "FINCILIA_OBJECT_STORE_ENDPOINT", value = "https://s3.${var.region}.amazonaws.com" },
      { name = "FINCILIA_OBJECT_REGION", value = var.region },
      { name = "FINCILIA_OBJECT_CREDENTIALS_SOURCE", value = "aws_workload_identity" },
      { name = "FINCILIA_REAL_DATA_ENABLED", value = "false" },
      { name = "FINCILIA_AI_GATEWAY_ENABLED", value = "false" },
      { name = "FINCILIA_PAYMENTS_ENABLED", value = "false" },
    ]
    secrets = [{
      name      = "FINCILIA_MIGRATOR_URL"
      valueFrom = "${aws_secretsmanager_secret.migrator.arn}:FINCILIA_MIGRATOR_URL::"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.runtime["migrator"].name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "migrator"
      }
    }
  }])
}

resource "aws_ecs_service" "application" {
  count = var.runtime_plane_enabled ? 1 : 0

  name                   = "${local.name}-application"
  cluster                = aws_ecs_cluster.pilot.id
  task_definition        = aws_ecs_task_definition.application[0].arn
  desired_count          = var.service_desired_count
  enable_execute_command = true
  wait_for_steady_state  = false

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }

  network_configuration {
    subnets          = aws_subnet.application[*].id
    security_groups  = [aws_security_group.application.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web[0].arn
    container_name   = "web"
    container_port   = 3000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    precondition {
      condition     = var.service_desired_count == 0
      error_message = "Foundation no puede arrancar servicios."
    }
  }
}

resource "aws_ecs_service" "worker" {
  count = var.runtime_plane_enabled ? 1 : 0

  name                   = "${local.name}-worker"
  cluster                = aws_ecs_cluster.pilot.id
  task_definition        = aws_ecs_task_definition.worker[0].arn
  desired_count          = var.service_desired_count
  enable_execute_command = true
  wait_for_steady_state  = false

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }

  network_configuration {
    subnets          = [aws_subnet.worker.id]
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    precondition {
      condition     = var.service_desired_count == 0
      error_message = "Foundation no puede arrancar servicios."
    }
  }
}
