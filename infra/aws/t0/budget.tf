resource "aws_budgets_budget" "gross_monthly" {
  name         = "fincilia-t0-gross-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.gross_monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = true
    include_recurring          = true
    include_refund             = false
    include_subscription       = true
    include_support            = true
    include_tax                = true
    include_upfront            = true
    use_amortized              = false
    use_blended                = false
  }
}
