# Global external HTTPS LB → serverless NEG → Cloud Run.
# Adds Cloud CDN, Cloud Armor, managed cert, HTTP→HTTPS redirect.

resource "google_compute_region_network_endpoint_group" "cloud_run" {
  project               = var.project_id
  name                  = "csoh-run-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.site.name
  }

  depends_on = [google_project_service.apis]
}

resource "google_compute_backend_service" "site" {
  depends_on            = [google_project_service.apis]
  project               = var.project_id
  name                  = "csoh-backend"
  protocol              = "HTTPS"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  enable_cdn = true
  cdn_policy {
    cache_mode                   = "CACHE_ALL_STATIC"
    default_ttl                  = 3600
    max_ttl                      = 86400
    client_ttl                   = 3600
    negative_caching             = true
    serve_while_stale            = 86400
    request_coalescing           = true
    signed_url_cache_max_age_sec = 0
  }

  security_policy = google_compute_security_policy.edge.id

  log_config {
    enable      = true
    sample_rate = 1.0
  }

  backend {
    group = google_compute_region_network_endpoint_group.cloud_run.id
  }
}

resource "google_compute_url_map" "site" {
  project         = var.project_id
  name            = "csoh-urlmap"
  default_service = google_compute_backend_service.site.id
}

# HTTP → HTTPS redirect URL map
resource "google_compute_url_map" "https_redirect" {
  project = var.project_id
  name    = "csoh-https-redirect"
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

# Managed TLS cert. STAGING ONLY for now — only gcp.csoh.org. We'll add
# csoh.org and www.csoh.org back when we're ready to cut prod DNS over.
# Changing the domain set forces cert recreation (and a brief HTTPS outage
# on hostnames covered by both the old and new cert).
resource "google_compute_managed_ssl_certificate" "site" {
  project = var.project_id
  name    = "csoh-cert-staging"
  managed {
    domains = [var.staging_domain]
  }
  lifecycle {
    create_before_destroy = true
  }
}

resource "google_compute_target_https_proxy" "site" {
  project          = var.project_id
  name             = "csoh-https-proxy"
  url_map          = google_compute_url_map.site.id
  ssl_certificates = [google_compute_managed_ssl_certificate.site.id]
  ssl_policy       = google_compute_ssl_policy.modern.id
}

resource "google_compute_target_http_proxy" "redirect" {
  project = var.project_id
  name    = "csoh-http-redirect-proxy"
  url_map = google_compute_url_map.https_redirect.id
}

# Modern TLS policy — TLS 1.2+, restricted cipher suite.
resource "google_compute_ssl_policy" "modern" {
  project         = var.project_id
  name            = "csoh-modern-tls"
  profile         = "MODERN"
  min_tls_version = "TLS_1_2"
}

resource "google_compute_global_address" "site" {
  project = var.project_id
  name    = "csoh-lb-ip"
}

resource "google_compute_global_forwarding_rule" "https" {
  project               = var.project_id
  name                  = "csoh-https-fr"
  target                = google_compute_target_https_proxy.site.id
  port_range            = "443"
  ip_address            = google_compute_global_address.site.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_forwarding_rule" "http" {
  project               = var.project_id
  name                  = "csoh-http-fr"
  target                = google_compute_target_http_proxy.redirect.id
  port_range            = "80"
  ip_address            = google_compute_global_address.site.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
