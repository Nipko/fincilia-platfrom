variable "region" {
  description = "Region autorizada para el control plane sintetico."
  type        = string
  default     = "sa-east-1"

  validation {
    condition     = var.region == "sa-east-1"
    error_message = "FNC-PLT-010 solo autoriza sa-east-1."
  }
}

variable "expected_account_id" {
  description = "Account ID esperado, aportado por entorno y nunca versionado."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id debe contener exactamente 12 digitos."
  }
}

variable "expires_at" {
  description = "Fecha de expiracion operativa del entorno T0."
  type        = string
  default     = "2026-09-27"
}
