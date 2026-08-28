variable "region" {
  description = "Region unica autorizada para T0."
  type        = string
  default     = "sa-east-1"

  validation {
    condition     = var.region == "sa-east-1"
    error_message = "FNC-PLT-010 solo autoriza sa-east-1."
  }
}
variable "expected_account_id" {
  description = "Account ID esperado; se aporta por entorno y no se versiona."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id debe contener exactamente 12 digitos."
  }
}

variable "expires_at" {
  description = "Fecha de expiracion operativa del control plane."
  type        = string
  default     = "2026-09-27"
}

variable "gross_monthly_budget_usd" {
  description = "Alerta mensual sobre gasto bruto antes de creditos."
  type        = number
  default     = 5

  validation {
    condition     = var.gross_monthly_budget_usd > 0 && var.gross_monthly_budget_usd <= 10
    error_message = "El presupuesto T0 debe estar entre USD 1 y USD 10."
  }
}
