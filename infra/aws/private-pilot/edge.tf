resource "aws_acm_certificate" "pilot" {
  domain_name       = var.pilot_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

resource "aws_lb" "pilot" {
  name                       = "fincilia-private-pilot"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  enable_deletion_protection = true
  drop_invalid_header_fields = true
  idle_timeout               = 60

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    prefix  = "alb"
    enabled = true
  }

  depends_on = [aws_s3_bucket_policy.alb_logs]
}

resource "aws_lb_target_group" "web" {
  name        = "fincilia-pilot-web"
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.pilot.id

  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = "/entrar"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.pilot.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.certificate_ready ? 1 : 0

  load_balancer_arn = aws_lb.pilot.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.pilot.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_wafv2_web_acl" "pilot" {
  name  = local.name
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSCommonRuleSet"
    priority = 10
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "fincilia-pilot-common"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "AWSKnownBadInputs"
    priority = 20
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "fincilia-pilot-bad-inputs"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "PerIpRateLimit"
    priority = 30
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type    = "IP"
        evaluation_window_sec = 300
        limit                 = 500
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "fincilia-pilot-rate"
      sampled_requests_enabled   = false
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "fincilia-private-pilot"
    sampled_requests_enabled   = false
  }
}

resource "aws_wafv2_web_acl_association" "pilot" {
  resource_arn = aws_lb.pilot.arn
  web_acl_arn  = aws_wafv2_web_acl.pilot.arn
}

resource "aws_cloudwatch_log_group" "waf" {
  name              = "aws-waf-logs-fincilia-private-pilot"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.audit.arn
}

resource "aws_wafv2_web_acl_logging_configuration" "pilot" {
  log_destination_configs = [aws_cloudwatch_log_group.waf.arn]
  resource_arn            = aws_wafv2_web_acl.pilot.arn

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }
  redacted_fields {
    single_header {
      name = "cookie"
    }
  }
}
