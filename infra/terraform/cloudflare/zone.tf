# Zone-level TLS posture. "strict" = Full (strict): Cloudflare validates the
# origin certificate on the Cloudflare→origin leg. All three origins present
# valid certs for their own hostnames (CloudFront default cert, run.app,
# Azure web endpoint), so strict works end-to-end — no unencrypted or
# unauthenticated hop anywhere. This replaces the GCP modern-TLS SSL policy.
resource "cloudflare_zone_settings_override" "site" {
  zone_id = var.zone_id

  settings {
    ssl                      = "strict"
    always_use_https         = "on"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    automatic_https_rewrites = "on"
    # HSTS and the other security headers are set explicitly in the response
    # header transform ruleset (rules.tf) so there is one source of truth that
    # mirrors nginx-security-headers.conf — we do NOT also enable the native
    # zone HSTS feature here, to avoid two systems setting the same header.
  }
}
