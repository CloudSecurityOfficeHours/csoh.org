# --- Background for newcomers -------------------------------------------------
# A "zone" in Cloudflare is one domain you manage there — here, csoh.org. This
# file tunes the zone-wide settings that control HOW Cloudflare talks to your
# visitors and to the three cloud origins (AWS, GCP, Azure) behind it.
# --
# A "resource" is a real thing Terraform creates or manages in the cloud (here,
# in Cloudflare). Terraform compares this desired state to what already exists
# and makes only the changes needed. (Contrast with a "data" source, used
# elsewhere, which only READS existing things and never changes them.) The
# provider — declared once in versions.tf as `provider "cloudflare" {}` — is the
# plugin that knows how to call Cloudflare's API; every cloudflare_* resource in
# this folder is created through it, authenticated by the CLOUDFLARE_API_TOKEN
# environment variable (no secret is stored in the repo).
# ------------------------------------------------------------------------------
# Zone-level TLS posture. "strict" = Full (strict): Cloudflare validates the
# origin certificate on the Cloudflare→origin leg. All three origins present
# valid certs for their own hostnames (CloudFront default cert, run.app,
# Azure web endpoint), so strict works end-to-end — no unencrypted or
# unauthenticated hop anywhere. This replaces the GCP modern-TLS SSL policy.
# This resource type, cloudflare_zone_settings_override, doesn't create a new
# object — it overrides a bundle of dials on the EXISTING csoh.org zone. The two
# words after the type ("site") are this resource's local Terraform name; other
# .tf files refer to it as cloudflare_zone_settings_override.site.
resource "cloudflare_zone_settings_override" "site" {
  # Which zone to apply these settings to. `var.zone_id` reads the input
  # variable `zone_id` declared in variables.tf — this is "interpolation," the
  # ${...}-style way Terraform plugs one value into another (here in its short
  # bare form, `var.zone_id`). Keeping the actual ID in a variable rather than
  # hardcoding it lets the same code target a different zone without edits.
  zone_id = var.zone_id

  # The settings {} block groups all the zone dials this resource manages.
  # Anything you set here is enforced by Terraform; anything you leave out keeps
  # whatever value the zone already has.
  settings {
    # TLS mode for the Cloudflare→origin hop. "strict" (a.k.a. Full (strict))
    # encrypts that hop AND verifies the origin's certificate, so a man-in-the-
    # middle can't impersonate an origin. See the block comment above for why all
    # three origins satisfy this.
    ssl = "strict"
    # Force every plain http:// request to redirect to https://. Visitors never
    # ride an unencrypted connection even if they type "http".
    always_use_https = "on"
    # Refuse the old, weak TLS 1.0/1.1 protocols; require at least TLS 1.2 on the
    # visitor→Cloudflare hop. A baseline modern-security setting.
    min_tls_version = "1.2"
    # Also allow the newest, faster, more secure protocol version, TLS 1.3, when
    # the visitor's browser supports it.
    tls_1_3 = "on"
    # Auto-rewrite http:// references INSIDE pages (images, scripts, links) to
    # https:// so a single insecure asset doesn't trip "mixed content" warnings.
    automatic_https_rewrites = "on"
    # HSTS and the other security headers are set explicitly in the response
    # header transform ruleset (rules.tf) so there is one source of truth that
    # mirrors nginx-security-headers.conf — we do NOT also enable the native
    # zone HSTS feature here, to avoid two systems setting the same header.
  }
}
