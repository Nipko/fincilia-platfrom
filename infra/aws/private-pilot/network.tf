resource "aws_vpc" "pilot" {
  cidr_block           = local.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags       = { Name = local.name }
  depends_on = [terraform_data.account_guard]
}

resource "aws_internet_gateway" "pilot" {
  vpc_id = aws_vpc.pilot.id
  tags   = { Name = local.name }
}

resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.pilot.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(local.vpc_cidr, 8, count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-public-${count.index + 1}", Tier = "public" }
}

resource "aws_subnet" "application" {
  count = 2

  vpc_id                  = aws_vpc.pilot.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(local.vpc_cidr, 8, 10 + count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-app-${count.index + 1}", Tier = "private-app" }
}

resource "aws_subnet" "worker" {
  vpc_id                  = aws_vpc.pilot.id
  availability_zone       = local.azs[0]
  cidr_block              = cidrsubnet(local.vpc_cidr, 8, 20)
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-worker-1", Tier = "isolated-worker" }
}

resource "aws_subnet" "data" {
  count = 2

  vpc_id                  = aws_vpc.pilot.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(local.vpc_cidr, 8, 30 + count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-data-${count.index + 1}", Tier = "isolated-data" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.pilot.id
  tags   = { Name = "${local.name}-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.pilot.id
}

resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  count = var.runtime_plane_enabled ? 1 : 0

  domain     = "vpc"
  depends_on = [aws_internet_gateway.pilot]
  tags       = { Name = "${local.name}-nat" }
}

resource "aws_nat_gateway" "application" {
  count = var.runtime_plane_enabled ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  depends_on    = [aws_internet_gateway.pilot]
  tags          = { Name = "${local.name}-app" }
}

resource "aws_route_table" "application" {
  count = 2

  vpc_id = aws_vpc.pilot.id
  tags   = { Name = "${local.name}-app-${count.index + 1}" }
}

resource "aws_route" "application_internet" {
  count = var.runtime_plane_enabled ? 2 : 0

  route_table_id         = aws_route_table.application[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.application[0].id
}

resource "aws_route_table_association" "application" {
  count = 2

  subnet_id      = aws_subnet.application[count.index].id
  route_table_id = aws_route_table.application[count.index].id
}

resource "aws_route_table" "worker" {
  vpc_id = aws_vpc.pilot.id
  tags   = { Name = "${local.name}-worker-no-default-route" }
}

resource "aws_route_table_association" "worker" {
  subnet_id      = aws_subnet.worker.id
  route_table_id = aws_route_table.worker.id
}

resource "aws_route_table" "data" {
  count = 2

  vpc_id = aws_vpc.pilot.id
  tags   = { Name = "${local.name}-data-${count.index + 1}-no-default-route" }
}

resource "aws_route_table_association" "data" {
  count = 2

  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data[count.index].id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.pilot.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids = concat(
    aws_route_table.application[*].id,
    [aws_route_table.worker.id],
  )
  tags = { Name = "${local.name}-s3" }
}

resource "aws_security_group" "endpoints" {
  name        = "${local.name}-endpoints"
  description = "PrivateLink solo desde el worker aislado"
  vpc_id      = aws_vpc.pilot.id
  egress      = []
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_worker" {
  security_group_id            = aws_security_group.endpoints.id
  referenced_security_group_id = aws_security_group.worker.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
}

resource "aws_vpc_endpoint" "worker_interface" {
  for_each = var.runtime_plane_enabled ? toset([
    "ecr.api", "ecr.dkr", "kms", "logs", "secretsmanager", "ssmmessages",
  ]) : toset([])

  vpc_id              = aws_vpc.pilot.id
  service_name        = "com.amazonaws.${var.region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [aws_subnet.worker.id]
  security_group_ids  = [aws_security_group.endpoints.id]
  tags                = { Name = "${local.name}-${replace(each.value, ".", "-")}" }
}

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Unica entrada publica del piloto"
  vpc_id      = aws_vpc.pilot.id
  egress      = []
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_security_group" "application" {
  name        = "${local.name}-application"
  description = "Web y API privados detras del ALB"
  vpc_id      = aws_vpc.pilot.id
  egress      = []
}

resource "aws_vpc_security_group_egress_rule" "alb_web" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.application.id
  from_port                    = 3000
  to_port                      = 3000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "application_alb" {
  security_group_id            = aws_security_group.application.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 3000
  to_port                      = 3000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "application_https" {
  security_group_id = aws_security_group.application.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Cognito y servicios AWS; nunca se asigna al worker"
}

resource "aws_vpc_security_group_egress_rule" "application_dns_udp" {
  security_group_id = aws_security_group.application.id
  cidr_ipv4         = local.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
}

resource "aws_vpc_security_group_egress_rule" "application_dns_tcp" {
  security_group_id = aws_security_group.application.id
  cidr_ipv4         = local.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
}

resource "aws_security_group" "worker" {
  name        = "${local.name}-worker"
  description = "Sin ingress ni salida general a Internet"
  vpc_id      = aws_vpc.pilot.id
  egress      = []
}

resource "aws_vpc_security_group_egress_rule" "worker_endpoints" {
  security_group_id            = aws_security_group.worker.id
  referenced_security_group_id = aws_security_group.endpoints.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "worker_s3" {
  security_group_id = aws_security_group.worker.id
  prefix_list_id    = aws_vpc_endpoint.s3.prefix_list_id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "worker_dns_udp" {
  security_group_id = aws_security_group.worker.id
  cidr_ipv4         = local.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
}

resource "aws_vpc_security_group_egress_rule" "worker_dns_tcp" {
  security_group_id = aws_security_group.worker.id
  cidr_ipv4         = local.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
}

resource "aws_security_group" "database" {
  name        = "${local.name}-database"
  description = "PostgreSQL solo desde app y worker"
  vpc_id      = aws_vpc.pilot.id
  egress      = []
}

resource "aws_vpc_security_group_ingress_rule" "database_application" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.application.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "database_worker" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.worker.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "application_database" {
  security_group_id            = aws_security_group.application.id
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "worker_database" {
  security_group_id            = aws_security_group.worker.id
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "cache" {
  name        = "${local.name}-cache"
  description = "Valkey solo desde app y worker"
  vpc_id      = aws_vpc.pilot.id
  egress      = []
}

resource "aws_vpc_security_group_ingress_rule" "cache_application" {
  security_group_id            = aws_security_group.cache.id
  referenced_security_group_id = aws_security_group.application.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "cache_worker" {
  security_group_id            = aws_security_group.cache.id
  referenced_security_group_id = aws_security_group.worker.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "application_cache" {
  security_group_id            = aws_security_group.application.id
  referenced_security_group_id = aws_security_group.cache.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "worker_cache" {
  security_group_id            = aws_security_group.worker.id
  referenced_security_group_id = aws_security_group.cache.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}
