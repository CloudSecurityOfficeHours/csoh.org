# --------------------------------------------------------------------------
# A monthly cost budget for this GCP project, with email alerts.
#
# Why this exists: the same reasoning as infra/terraform/aws/budget.tf, with the
# same $10 limit and the same alert address. GCP has the sharpest history of
# the three clouds. Its promotional credits ran out mid-day on 2026-07-28, the
# project went from exactly $0.00 a day to about $2.25 a day with nothing in the
# deployment changing, and nobody noticed for four weeks. A budget that counts
# cost after credits (the default, kept here) would have fired within days.
#
# Three things about it are easy to get wrong:
#   - A budget belongs to the BILLING ACCOUNT, not to the project; the project
#     is only a filter. So whoever runs Terraform needs a billing role on that
#     account (billing.admin or billing.costsManager). Project Owner is not
#     enough.
#   - The Budget API is billed against a "quota project", and a person's own
#     application-default credentials may not name one, which fails with an
#     error about a missing quota project. The `google.billing` provider alias
#     in versions.tf names ours explicitly.
#   - The APIs this needs (see apis.tf) must be enabled in that quota project
#     BEFORE this file can even be planned, because the data source below is
#     read at plan time. On a first apply, enable the APIs, wait a minute, then
#     apply this file.
# --------------------------------------------------------------------------

# Where the alerts go. A Cloud Monitoring "notification channel" is a reusable
# destination; this creates one email channel per address in the variable.
resource "google_monitoring_notification_channel" "budget_email" {
  # for_each makes one channel per address. toset() turns the list into the set
  # type for_each expects, and each.value is the address for that copy.
  for_each     = toset(var.budget_alert_emails)
  display_name = "Budget alerts (${each.value})"
  type         = "email"
  labels = {
    email_address = each.value
  }
}

# Which billing account this project is linked to, looked up rather than
# written into a public repository. If the project is ever moved to another
# billing account, the budget follows it on the next apply.
data "google_project" "billing" {
  provider   = google.billing
  project_id = var.project_id
}

resource "google_billing_budget" "monthly" {
  provider        = google.billing
  billing_account = data.google_project.billing.billing_account
  display_name    = "csoh-monthly-cost"

  budget_filter {
    # Count this project only. Budget filters name projects by NUMBER, not ID.
    projects = ["projects/${var.project_number}"]
    # Count cost after every kind of credit - promotional credits and the
    # monthly free tier alike - so the budget tracks what is actually billed.
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "USD"
      # A few times what the project should bill now that the health probes
      # come from one region and the registry keeps its newest 10 images.
      units = "10"
    }
  }

  # Alert at half the limit, at the limit, and when Google FORECASTS the month
  # will pass the limit (the early warning). threshold_percent is a fraction:
  # 0.5 means 50%.
  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 1.0
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [for c in google_monitoring_notification_channel.budget_email : c.id]
    # Keep Google's default recipients as well: the billing account's admins
    # get the same email, so an alert still lands if the channel address ever
    # stops working.
    disable_default_iam_recipients = false
  }

  # The Budget API has to be switched on before the budget can be created.
  depends_on = [google_project_service.apis]
}
