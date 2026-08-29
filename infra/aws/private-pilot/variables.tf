variable "region" {
  type    = string
  default = "sa-east-1"
  validation {
    condition     = var.region == "sa-east-1"
    error_message = "FNC-PLT-012 solo autoriza sa-east-1."
  }
}

variable "expected_account_id" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id debe contener 12 digitos."
  }
}

variable "pilot_domain" {
  type    = string
  default = "pilot.example.invalid"
  validation {
    condition = length(var.pilot_domain) <= 253 && can(regex(
      "^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$", var.pilot_domain
    ))
    error_message = "pilot_domain debe ser un FQDN DNS en minusculas."
  }
}

variable "cognito_domain_prefix" {
  type    = string
  default = "fincilia-private-pilot-placeholder"
  validation {
    condition     = can(regex("^[a-z0-9-]{8,63}$", var.cognito_domain_prefix))
    error_message = "cognito_domain_prefix debe usar minusculas, numeros y guiones."
  }
}

variable "release_sha" {
  type    = string
  default = "0000000000000000000000000000000000000000"
  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.release_sha))
    error_message = "release_sha debe ser un SHA Git completo."
  }
}

variable "api_image" {
  type    = string
  default = "000000000000.dkr.ecr.sa-east-1.amazonaws.com/fincilia/private-pilot/api@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.sa-east-1\\.amazonaws\\.com/[a-z0-9/_-]+@sha256:[0-9a-f]{64}$", var.api_image))
    error_message = "api_image debe ser ECR sa-east-1 fijada por digest."
  }
}

variable "web_image" {
  type    = string
  default = "000000000000.dkr.ecr.sa-east-1.amazonaws.com/fincilia/private-pilot/web@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.sa-east-1\\.amazonaws\\.com/[a-z0-9/_-]+@sha256:[0-9a-f]{64}$", var.web_image))
    error_message = "web_image debe ser ECR sa-east-1 fijada por digest."
  }
}

variable "worker_image" {
  type    = string
  default = "000000000000.dkr.ecr.sa-east-1.amazonaws.com/fincilia/private-pilot/worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.sa-east-1\\.amazonaws\\.com/[a-z0-9/_-]+@sha256:[0-9a-f]{64}$", var.worker_image))
    error_message = "worker_image debe ser ECR sa-east-1 fijada por digest."
  }
}

variable "certificate_ready" {
  description = "Solo true despues de publicar y verificar el challenge DNS de ACM."
  type        = bool
  default     = false
}

variable "runtime_plane_enabled" {
  description = "Crea el plano temporal facturable; cold=false es el valor seguro."
  type        = bool
  default     = false
}

variable "service_desired_count" {
  description = "Foundation siempre crea servicios detenidos; activacion es otra tarea/gate."
  type        = number
  default     = 0
  validation {
    condition     = var.service_desired_count == 0
    error_message = "FNC-PLT-012 foundation exige desired_count=0."
  }
}

variable "gross_monthly_budget_usd" {
  type    = number
  default = 120
  validation {
    condition     = var.gross_monthly_budget_usd >= 60 && var.gross_monthly_budget_usd <= 250
    error_message = "El presupuesto piloto debe quedar entre USD 60 y USD 250."
  }
}

variable "budget_alert_email" {
  description = "Buzon operativo para alertas AWS Budgets; se suministra fuera del repositorio."
  type        = string
  sensitive   = true
  validation {
    condition = length(var.budget_alert_email) <= 254 && can(regex(
      "^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.budget_alert_email
    ))
    error_message = "budget_alert_email debe ser un correo operativo valido."
  }
}

variable "expires_at" {
  type    = string
  default = "2027-02-15"
}
