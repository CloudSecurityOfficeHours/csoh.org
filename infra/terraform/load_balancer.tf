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

# Managed TLS cert — gcp.csoh.org only.
#
# Production hostnames (csoh.org, www.csoh.org) are served via Cloudflare
# proxy mode. Cloudflare terminates browser TLS with its own Universal SSL
# cert, then proxies to this LB on origin. The GCP managed cert therefore
# only needs to cover the staging hostname that hits the LB directly via
# DNS-only Cloudflare records.
#
# Why we don't put csoh.org / www.csoh.org in this cert: Google managed
# cert validation uses HTTP-01 ACME, which requires the domain to resolve
# directly to the LB. While Cloudflare is in proxy mode for those names,
# the validator can't see the LB and the cert hangs in FAILED_NOT_VISIBLE.
# We chose the proxy architecture (instead of gray-cloud direct DNS)
# because it eliminates the TLS-error window during cert recreation and
# absorbs traffic at Cloudflare's edge before it ever reaches our origin.
# Trade-off documented in cloud-deployment.html.
#
# `create_before_destroy` ensures Terraform creates a new cert and swaps
# the target_https_proxy over before destroying the old cert (avoids the
# "cert in use, cannot delete" cascade).
resource "google_compute_managed_ssl_certificate" "site" {
  project = var.project_id
  name    = "csoh-cert-staging-only"
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
