# ---------------------------------------------------------------------------
# WHAT THIS FILE DOES
# This Terraform file sets up log storage and log routing for the GCP origin.
# Google Cloud Logging is GCP's built-in service that collects logs from your
# cloud resources (here, the Cloud Run container that serves the website). By
# default GCP keeps those logs only ~30 days. This file (1) creates a log
# "bucket" that keeps chosen logs much longer, and (2) creates a "sink" — a
# rule that copies matching log entries into that long-retention bucket.
#
# TERRAFORM CONCEPTS (taught once, here):
# - A "resource" block describes one real thing in the cloud that Terraform
#   will create and manage for you. The two words after `resource` are the
#   resource TYPE (e.g. google_logging_project_bucket_config) and a local
#   NAME you pick (e.g. long_retention) used only to refer to it elsewhere in
#   this Terraform code.
# - `var.project_id` reads an input VARIABLE defined in variables.tf. Its
#   value here is the GCP project ID "csoh-org-495800". Variables let the
#   same code be reused without hard-coding values in every file.
# - `${...}` is INTERPOLATION: it injects a value into the middle of a string.
#   Referencing one resource's attribute inside another (as the sink does
#   below) also tells Terraform the correct order to create them in.
#
# NOTE: there is no `terraform {}`, `provider {}`, or `backend {}` block in
# this file. Those live once in versions.tf and apply to every .tf file in
# this directory (Terraform reads them all together as one configuration).
# ---------------------------------------------------------------------------

# A LOG BUCKET is a named container inside Cloud Logging that stores log
# entries (it is NOT a Cloud Storage / object-storage bucket — same word,
# different service). Its main knob is how long entries are kept before being
# auto-deleted. GCP auto-creates a "_Default" bucket that retains logs only
# 30 days; this resource adds a second bucket with a much longer (400-day)
# retention for access logs and audit logs, so security-relevant logs survive
# long enough to investigate an incident ("forensics") or demonstrate the
# setup ("showcase").
resource "google_logging_project_bucket_config" "long_retention" {
  # Which GCP project this log bucket belongs to (read from variables.tf).
  project = var.project_id
  # Where the bucket lives. "global" is a valid Cloud Logging location that
  # is not tied to one geographic region — appropriate for project-wide logs.
  location = "global"
  # The bucket's fixed ID/name within the project. We reference this exact
  # string from the sink below, so its destination always points here.
  bucket_id = "csoh-long-retention"
  # Keep every log entry in this bucket for 400 days before auto-deletion,
  # versus the 30-day default. 400 comfortably exceeds a full year.
  retention_days = 400
  # Free-text label shown in the GCP Console so a human knows what it's for.
  description = "Long-term retention for security-relevant logs"
}

# A LOG SINK is a routing rule: "for log entries matching this filter, send a
# copy to this destination." Cloud Logging evaluates every incoming log entry
# against all sinks. This sink selects security-relevant entries and copies
# them into the long-retention bucket created above, so they outlive the
# 30-day default even though the originals still expire from _Default.
resource "google_logging_project_sink" "security" {
  # Which project's logs this sink watches (read from variables.tf).
  project = var.project_id
  # Name of the sink as it appears in the project's logging config.
  name = "csoh-security-sink"
  # Where matching log entries are copied. This is the full resource path of
  # the log bucket above. Two interpolations build it:
  #   - ${var.project_id} inserts the project ID, and
  #   - ${google_logging_project_bucket_config.long_retention.bucket_id} reads
  #     the bucket_id off the bucket resource defined earlier. Referencing the
  #     bucket this way also makes Terraform create the bucket BEFORE this sink
  #     automatically — the dependency is inferred, no manual ordering needed.
  destination = "logging.googleapis.com/projects/${var.project_id}/locations/global/buckets/${google_logging_project_bucket_config.long_retention.bucket_id}"

  # `filter` is the matching rule, written in Cloud Logging's query language;
  # only entries matching it get routed. (The Cloud Armor / LB clauses were
  # dropped with the GCLB — edge WAF + error logging now live in Cloudflare's
  # zone analytics/logs.) The `<<-EOT ... EOT` syntax is a "heredoc" — a tidy
  # way to write a multi-line string; the leading dash lets the lines be
  # indented for readability without the indentation becoming part of the
  # string. The three OR'd clauses below match, in order:
  #   1. Cloud Run requests whose HTTP status is 400 or higher (client/server
  #      errors) — useful signal about origin problems and probing.
  #   2. Any log produced by the IAM service (iam.googleapis.com), i.e. changes
  #      to who-can-do-what permissions.
  #   3. Audit Logs (the @type tag marks an entry as a Cloud Audit Log), which
  #      record administrative "who did what, when" activity in the project.
  filter = <<-EOT
    (resource.type="cloud_run_revision" AND httpRequest.status>=400)
    OR protoPayload.serviceName="iam.googleapis.com"
    OR protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"
  EOT

  # A sink writes into its destination using a service account — a non-human
  # "robot" identity that GCP services use to act on each other. Setting this
  # to true makes GCP mint a DEDICATED service account just for this sink
  # (instead of a single shared one used by all sinks). That dedicated
  # identity can then be granted permission to write only into this one
  # bucket — a least-privilege practice (give each component the narrowest
  # access it needs). After apply, this identity is exposed as the sink's
  # `writer_identity` attribute so a separate IAM grant can authorize it.
  unique_writer_identity = true
}
