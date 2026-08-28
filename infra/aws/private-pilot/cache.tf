resource "aws_elasticache_subnet_group" "pilot" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_elasticache_parameter_group" "pilot" {
  name   = "${local.name}-valkey8"
  family = "valkey8"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
}

resource "aws_elasticache_replication_group" "pilot" {
  replication_group_id = local.name
  description          = "Cache efimero; nunca autoridad financiera"

  engine         = "valkey"
  engine_version = "8.1"
  node_type      = "cache.t4g.micro"
  port           = 6379

  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false

  subnet_group_name    = aws_elasticache_subnet_group.pilot.name
  parameter_group_name = aws_elasticache_parameter_group.pilot.name
  security_group_ids   = [aws_security_group.cache.id]

  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.database.arn

  snapshot_retention_limit = 0
  apply_immediately        = false
  maintenance_window       = "sun:08:00-sun:09:00"
}
