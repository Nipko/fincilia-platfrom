provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "Fincilia"
      Environment = "private-pilot"
      DataClass   = "real_pending_DRG-01"
      ManagedBy   = "OpenTofu"
      Task        = "FNC-PLT-012"
      ExpiresAt   = var.expires_at
      Owner       = "FOUNDER-01"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_partition" "current" {}

resource "terraform_data" "account_guard" {
  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "La sesion AWS no corresponde a la cuenta autorizada."
    }
    precondition {
      condition     = data.aws_region.current.region == "sa-east-1"
      error_message = "La sesion AWS no corresponde a sa-east-1."
    }
    precondition {
      condition     = var.pilot_domain != "pilot.example.invalid"
      error_message = "No se puede aplicar el dominio placeholder."
    }
    precondition {
      condition     = var.cognito_domain_prefix != "fincilia-private-pilot-placeholder"
      error_message = "No se puede aplicar el prefijo Cognito placeholder."
    }
    precondition {
      condition     = var.release_sha != "0000000000000000000000000000000000000000"
      error_message = "No se puede aplicar un release placeholder."
    }
  }
}

locals {
  name     = "fincilia-private-pilot"
  vpc_cidr = "10.60.0.0/16"
  azs      = slice(data.aws_availability_zones.available.names, 0, 2)
  registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}
