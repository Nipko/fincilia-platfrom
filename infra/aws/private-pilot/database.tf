resource "aws_db_subnet_group" "pilot" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
  tags       = { Name = local.name }
}

resource "aws_db_parameter_group" "pilot" {
  name   = "${local.name}-postgres17"
  family = "postgres17"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "log_connections"
    value        = "1"
    apply_method = "immediate"
  }

  parameter {
    name         = "log_disconnections"
    value        = "1"
    apply_method = "immediate"
  }
}

resource "aws_db_instance" "pilot" {
  identifier = local.name

  engine         = "postgres"
  engine_version = "17.11"
  instance_class = "db.t4g.micro"

  db_name  = "fincilia_pilot"
  username = "fincilia_pilot_admin"
  port     = 5432

  manage_master_user_password   = true
  master_user_secret_kms_key_id = aws_kms_key.database.arn

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.database.arn

  db_subnet_group_name   = aws_db_subnet_group.pilot.name
  parameter_group_name   = aws_db_parameter_group.pilot.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period    = 14
  backup_window              = "05:00-06:00"
  maintenance_window         = "sun:06:30-sun:07:30"
  auto_minor_version_upgrade = false
  apply_immediately          = false

  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = false
  monitoring_interval             = 0

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name}-final"
  copy_tags_to_snapshot     = true

  lifecycle {
    prevent_destroy = true
  }
}
