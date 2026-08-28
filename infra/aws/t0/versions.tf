terraform {
  required_version = "= 1.12.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.59.0"
    }
  }

  backend "s3" {
    key          = "fincilia/t0/control-plane.tfstate"
    region       = "sa-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
