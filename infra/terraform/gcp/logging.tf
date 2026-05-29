# Long-term retention bucket for access logs and audit logs. Default
# _Default sink only retains 30d; this gives 400d for showcase / forensics.
resource "google_logging_project_bucket_config" "long_retention" {
  project        = var.project_id
  location       = "global"
  bucket_id      = "csoh-long-retention"
  retention_days = 400
  description    = "Long-term retention for security-relevant logs"
}

resource "google_logging_project_sink" "security" {
  project     = var.project_id
  name        = "csoh-security-sink"
  destination = "logging.googleapis.com/projects/${var.project_id}/locations/global/buckets/${google_logging_project_bucket_config.long_retention.bucket_id}"

  # Capture: Cloud Run requests with non-2xx, IAM policy changes, admin
  # activity. (The Cloud Armor / LB clauses were dropped with the GCLB —
  # edge WAF + error logging now live in Cloudflare's zone analytics/logs.)
  filter = <<-EOT
    (resource.type="cloud_run_revision" AND httpRequest.status>=400)
    OR protoPayload.serviceName="iam.googleapis.com"
    OR protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"
  EOT

  unique_writer_identity = true
}
