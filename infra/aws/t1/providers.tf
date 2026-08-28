provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "Fincilia"
      Environment = "t1-remote-lab"
      DataClass   = "synthetic_only"
      ManagedBy   = "OpenTofu"
      Task        = "FNC-PLT-011"
      ExpiresAt   = var.expires_at
      Owner       = "FOUNDER-01"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "terraform_remote_state" "t0" {
  backend = "s3"
  config = {
    bucket = var.state_bucket_name
    key    = "fincilia/t0/control-plane.tfstate"
    region = var.region
  }
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
  }
}

locals {
  bundle_prefix = "deployment/${var.release_sha}"
  registry      = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}
