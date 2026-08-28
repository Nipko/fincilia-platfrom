resource "aws_security_group" "beta" {
  name        = "fincilia-closed-beta"
  description = "Solo HTTPS publico y redireccion HTTP; administracion por SSM"
  vpc_id      = data.terraform_remote_state.t0.outputs.vpc_id

  ingress {
    description = "ACME y redireccion HTTP a HTTPS"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Aplicacion beta por HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Bootstrap, SSM, ECR, S3, DNS y ACME; workloads aislados por redes Docker"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "fincilia-closed-beta" }

  depends_on = [terraform_data.account_guard]
}

resource "aws_eip" "beta" {
  domain = "vpc"
  tags   = { Name = "fincilia-closed-beta" }

  depends_on = [terraform_data.account_guard]
}

resource "aws_eip_association" "beta" {
  instance_id   = aws_instance.beta.id
  allocation_id = aws_eip.beta.id
}
