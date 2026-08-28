resource "aws_vpc" "t0" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "fincilia-t0" }

  depends_on = [terraform_data.account_guard]
}

resource "aws_internet_gateway" "t0" {
  vpc_id = aws_vpc.t0.id
  tags   = { Name = "fincilia-t0" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.t0.id
  cidr_block              = "10.42.0.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = { Name = "fincilia-t0-public-a", Tier = "public" }
}

resource "aws_subnet" "private" {
  count = 2

  vpc_id                  = aws_vpc.t0.id
  cidr_block              = cidrsubnet("10.42.0.0/16", 8, 10 + count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "fincilia-t0-private-${count.index + 1}", Tier = "private" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.t0.id
  tags   = { Name = "fincilia-t0-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.t0.id
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count = 2

  vpc_id = aws_vpc.t0.id
  tags   = { Name = "fincilia-t0-private-${count.index + 1}" }
}

resource "aws_route_table_association" "private" {
  count = 2

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.t0.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id
  tags              = { Name = "fincilia-t0-s3" }
}

resource "aws_security_group" "runtime" {
  name        = "fincilia-t0-runtime"
  description = "Sin ingress; reservado para runtime posterior no desplegado en FNC-PLT-010"
  vpc_id      = aws_vpc.t0.id

  egress {
    description = "HTTPS hacia servicios administrados"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "fincilia-t0-runtime" }
}

resource "aws_security_group" "database" {
  name        = "fincilia-t0-database"
  description = "Solo PostgreSQL desde el SG runtime; no crea una base de datos"
  vpc_id      = aws_vpc.t0.id

  ingress {
    description     = "PostgreSQL desde runtime"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.runtime.id]
  }

  egress = []
  tags   = { Name = "fincilia-t0-database" }
}
