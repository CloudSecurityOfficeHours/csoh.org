# --------------------------------------------------------------------------
# A monthly cost budget for this AWS account, with email alerts.
#
# Why this exists: without it, a cost problem (credits running out, a health
# check multiplied across every probe source, storage that grows without
# expiry) surfaces only when a person reads a bill, weeks after it started. A
# budget is the cheapest instrument that speaks up on its own. AWS charges nothing for a
# budget that only sends notifications (only "action-enabled" budgets beyond
# the first two cost money), so this one is free to run.
#
# What it measures. A budget counts cost AFTER credits unless told otherwise,
# and this one keeps that default on purpose. While the account's promotional
# credit lasts it cancels all usage, so the budget reads $0.00. That turns the first alert below
# into a tripwire: the first dollar AWS actually bills means the credits have
# run out, or something new is running.
#
# Applied by hand, like everything in this stack. `aws login` sessions are not
# something the Terraform provider can use; export them first (CLAUDE.md):
#   eval "$(aws configure export-credentials --format env)"
#   terraform apply -target=aws_budgets_budget.monthly
# --------------------------------------------------------------------------
resource "aws_budgets_budget" "monthly" {
  # Name shown in the Billing console. Budgets belong to the account and are
  # global, so there is no region involved.
  name = "csoh-monthly-cost"
  # COST budgets track dollars (other types track usage or reservations).
  budget_type = "COST"
  # The monthly limit the percentages below are measured against. $10 is a
  # few times what this account should bill once the credits are gone, so a
  # normal month stays quiet and a real regression does not: for scale, the
  # health-probe traffic alone cost CloudFront $18.26 in August 2026.
  limit_amount = "10"
  limit_unit   = "USD"
  # Start counting again at the beginning of every calendar month.
  time_unit = "MONTHLY"

  # Alert 1: actual spend passes 10% of the limit, i.e. the first dollar that
  # credits did not cover. See "What it measures" above.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 10
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_alert_emails
  }

  # Alert 2: actual spend passes the whole $10.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_alert_emails
  }

  # Alert 3: AWS FORECASTS that the month will pass $10. This is the early
  # warning - it can fire in the first week of a bad month instead of after it.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.budget_alert_emails
  }
}
