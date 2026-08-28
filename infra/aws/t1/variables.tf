variable "region" {
  type    = string
  default = "sa-east-1"
  validation {
    condition     = var.region == "sa-east-1"
    error_message = "FNC-PLT-011 solo autoriza sa-east-1."
  }
}

variable "expected_account_id" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id debe contener exactamente 12 digitos."
  }
}

variable "state_bucket_name" {
  description = "Bucket T0 del estado, aportado localmente y no versionado."
  type        = string
  sensitive   = true
}

variable "release_sha" {
  description = "SHA Git completo que identifica las imagenes y el bundle."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.release_sha))
    error_message = "release_sha debe ser un SHA Git completo."
  }
}

variable "api_image" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+\\.dkr\\.ecr\\.sa-east-1\\.amazonaws\\.com/fincilia/t0/api@sha256:[0-9a-f]{64}$", var.api_image))
    error_message = "api_image debe ser el ECR T0 por digest."
  }
}

variable "web_image" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+\\.dkr\\.ecr\\.sa-east-1\\.amazonaws\\.com/fincilia/t0/web@sha256:[0-9a-f]{64}$", var.web_image))
    error_message = "web_image debe ser el ECR T0 por digest."
  }
}

variable "worker_image" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+\\.dkr\\.ecr\\.sa-east-1\\.amazonaws\\.com/fincilia/t0/worker@sha256:[0-9a-f]{64}$", var.worker_image))
    error_message = "worker_image debe ser el ECR T0 por digest."
  }
}

variable "expires_at" {
  type    = string
  default = "2026-09-27"
}
