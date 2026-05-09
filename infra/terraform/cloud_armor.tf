# Cloud Armor edge policy — WAF + rate limiting in front of Cloud Run.
# Uses preconfigured WAF rules at sensitivity level 1 (lowest false-positive
# rate). For a static site this is more about demonstrating the control
# than blocking real attacks.
resource "google_compute_security_policy" "edge" {
  project     = var.project_id
  name        = "csoh-edge-policy"
  description = "WAF + rate limiting for csoh.org"
  type        = "CLOUD_ARMOR"

  # OWASP CRS — SQLi
  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})"
      }
    }
    description = "Block SQLi (OWASP CRS sensitivity 1)"
  }

  # OWASP CRS — XSS
  rule {
    action   = "deny(403)"
    priority = 1010
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})"
      }
    }
    description = "Block XSS (OWASP CRS sensitivity 1)"
  }

  # OWASP CRS — LFI / RFI / RCE
  rule {
    action   = "deny(403)"
    priority = 1020
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('lfi-v33-stable', {'sensitivity': 1})"
      }
    }
    description = "Block LFI"
  }

  rule {
    action   = "deny(403)"
    priority = 1030
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('rfi-v33-stable', {'sensitivity': 1})"
      }
    }
    description = "Block RFI"
  }

  rule {
    action   = "deny(403)"
    priority = 1040
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('rce-v33-stable', {'sensitivity': 1})"
      }
    }
    description = "Block RCE"
  }

  # Per-IP rate limit — 600 req/min, ban for 10m if exceeded.
  rule {
    action   = "rate_based_ban"
    priority = 2000
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 600
        interval_sec = 60
      }
      ban_duration_sec = 600
    }
    description = "Per-IP rate limit: 600 req/min, 10-minute ban on exceed"
  }

  # Default allow.
  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default rule, allow"
  }

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable          = true
      rule_visibility = "STANDARD"
    }
  }
}
