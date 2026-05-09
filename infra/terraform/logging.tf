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

  # Capture: Cloud Armor blocks + denies, LB requests with non-2xx,
  # IAM policy changes, admin activity.
  filter = <<-EOT
    (resource.type="http_load_balancer" AND jsonPayload.enforcedSecurityPolicy.outcome="DENY")
    OR (resource.type="http_load_balancer" AND httpRequest.status>=400)
    OR protoPayload.serviceName="iam.googleapis.com"
    OR protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"
  EOT

  unique_writer_identity = true
}
