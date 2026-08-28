provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "Fincilia"
      Environment = "t0-synthetic"
      DataClass   = "synthetic_only"
      ManagedBy   = "OpenTofu"
      Task        = "FNC-PLT-010"
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
      condition     = length(data.aws_availability_zones.available.names) >= 2
      error_message = "T0 requiere al menos dos zonas disponibles en sa-east-1."
    }
  }
}

locals {
  account_suffix = data.aws_caller_identity.current.account_id
  object_bucket  = "fincilia-${local.account_suffix}-t0-objects-${var.region}"
  trail_bucket   = "fincilia-${local.account_suffix}-t0-trail-${var.region}"
}
