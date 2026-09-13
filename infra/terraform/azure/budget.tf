# --------------------------------------------------------------------------
# A monthly cost budget for the Azure subscription, with email alerts.
#
# Why this exists: the same reasoning as infra/terraform/aws/budget.tf, with the
# same $10 limit and the same alert address. Azure has its own history here:
# the July 2026 bill carried $119.77 of bandwidth that nobody saw until August,
# because a health check was downloading the home page from every Cloudflare
# data center. A budget would have said so in the first week of July. Azure
# budgets cost nothing.
#
# The scope is the whole subscription, not just the "csoh-site" resource group,
# so anything created outside that group is counted too.
# --------------------------------------------------------------------------
resource "azurerm_consumption_budget_subscription" "monthly" {
  # Name shown under Cost Management -> Budgets.
  name = "csoh-monthly-cost"
  # The subscription to watch, written as a full Azure resource ID
  # ("/subscriptions/<id>") and built from the same variable versions.tf uses
  # to pin the provider, so the budget cannot land on a different subscription.
  subscription_id = "/subscriptions/${var.subscription_id}"
  # Monthly limit, in the billing currency (USD). A few times the ~$3 a month
  # this subscription should bill now that the health probes come from one
  # region, so a normal month stays quiet.
  amount = 10
  # Start counting again every calendar month.
  time_grain = "Monthly"

  time_period {
    # Azure requires the first day of a month here. Changing it later replaces
    # the budget and throws away its history, so leave it alone.
    start_date = "2026-09-01T00:00:00Z"
  }

  # Alert 1: actual spend passes half the limit ($5).
  notification {
    enabled        = true
    operator       = "GreaterThan"
    threshold      = 50
    threshold_type = "Actual"
    contact_emails = var.budget_alert_emails
  }

  # Alert 2: actual spend passes the whole limit.
  notification {
    enabled        = true
    operator       = "GreaterThan"
    threshold      = 100
    threshold_type = "Actual"
    contact_emails = var.budget_alert_emails
  }

  # Alert 3: Azure FORECASTS that the month will pass the limit. This is the
  # early warning, and the one that would have caught July's bandwidth bill.
  notification {
    enabled        = true
    operator       = "GreaterThan"
    threshold      = 100
    threshold_type = "Forecasted"
    contact_emails = var.budget_alert_emails
  }
}
