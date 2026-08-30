resource "aws_cloudwatch_metric_alarm" "instance_status" {
  alarm_name          = "fincilia-closed-beta-instance-status"
  alarm_description   = "La instancia de beta cerrada fallo su status check."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  dimensions          = { InstanceId = aws_instance.beta.id }
}

resource "aws_cloudwatch_metric_alarm" "backup_freshness" {
  alarm_name          = "fincilia-closed-beta-backup-freshness"
  alarm_description   = "No se observo un backup sintetico exitoso en 36 horas."
  namespace           = "Fincilia/ClosedBeta"
  metric_name         = "BackupSuccess"
  statistic           = "Maximum"
  period              = 43200
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
}

resource "aws_cloudwatch_metric_alarm" "restore_check" {
  alarm_name          = "fincilia-closed-beta-restore-check"
  alarm_description   = "No se observo restore-check exitoso durante siete dias."
  namespace           = "Fincilia/ClosedBeta"
  metric_name         = "RestoreCheckSuccess"
  statistic           = "Maximum"
  period              = 86400
  evaluation_periods  = 7
  datapoints_to_alarm = 7
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
}

resource "aws_budgets_budget" "beta" {
  name         = "fincilia-closed-beta-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.gross_monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = true
    include_recurring          = true
    include_refund             = false
    include_subscription       = true
    include_support            = true
    include_tax                = true
    include_upfront            = true
    use_amortized              = false
    use_blended                = false
  }

}
