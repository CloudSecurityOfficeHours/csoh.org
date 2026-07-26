# =============================================================================
# CAA - which certificate authorities may issue for csoh.org
# -----------------------------------------------------------------------------
# A CAA record (RFC 8659) is the only mechanism that constrains WHICH CAs may
# issue a certificate for a domain. With no CAA record, every publicly trusted
# CA on earth - roughly fifty - is permitted, and any one of them mis-issuing,
# or being tricked during domain validation by a transient DNS or BGP hijack,
# produces a certificate browsers accept.
#
# HSTS preload does not help with this. A preloaded domain still trusts any
# publicly trusted chain; it forces HTTPS, it does not say whose HTTPS.
#
# CAA is checked by the CA at issuance, over plain DNS. That makes it only as
# trustworthy as the DNS answer carrying it, which is the argument for DNSSEC
# in dns_dnssec.tf: without signing, an attacker who can forge a DNS response
# strips these restrictions and obtains a certificate from an excluded CA.
# =============================================================================

# These records were originally created through the Cloudflare dashboard's
# "add recommended CAA records" helper, which publishes Cloudflare's full
# supported-CA set. They are declared here to bring them under version control
# and stop them drifting silently, so the values below MIRROR WHAT IS ALREADY
# LIVE rather than proposing something new. Import before the first apply (see
# infra/MANUAL_SECURITY_STEPS.md section 3) or Terraform will create a second
# copy of each.
#
# ON THE SIZE OF THIS LIST. Five CAs is more permissive than strictly needed:
# the certificate actually being served is from Let's Encrypt, and a minimal
# pin would name only that. Cloudflare recommends the wider set because it
# chooses and rotates the issuing CA itself, and on the Free plan there is no
# setting to fix it (that is an Advanced Certificate Manager feature). A pin
# that is too narrow does not fail at apply time - it fails months later when a
# renewal is refused, and stays quiet until the existing certificate expires.
#
# Five instead of ~fifty is where nearly all of the security benefit lives.
# Narrow it only if you move to Advanced Certificate Manager and select the CA
# explicitly, and in that case ADD the new CA here BEFORE switching.
locals {
  # Keys are arbitrary local labels used for the Terraform resource addresses
  # and for import; the values are the exact CAA property strings served today.
  # `cansignhttpexchanges=yes` is a CAA parameter permitting Signed HTTP
  # Exchanges; it is part of Cloudflare's published set and is kept verbatim so
  # this configuration matches the live records byte for byte.
  caa_authorized_cas = {
    comodoca    = "comodoca.com"
    digicert    = "digicert.com; cansignhttpexchanges=yes"
    letsencrypt = "letsencrypt.org"
    pkigoog     = "pki.goog; cansignhttpexchanges=yes"
    sslcom      = "ssl.com"
  }
}

# --- issue: CAs authorised to issue ordinary (non-wildcard) certificates.
resource "cloudflare_record" "caa_issue" {
  for_each = local.caa_authorized_cas

  zone_id = var.zone_id
  name    = var.zone_name
  type    = "CAA"
  ttl     = 3600

  data {
    # flags=0 means "not critical": a CA that does not understand this record
    # may proceed rather than refusing outright. 0 is the normal value.
    flags = 0
    tag   = "issue"
    value = each.value
  }
}

# --- issuewild: CAs authorised to issue WILDCARD certificates.
#
# This half is load-bearing and easy to get catastrophically wrong. Cloudflare
# Universal SSL issues a WILDCARD certificate for this domain - verified
# against the live endpoint:
#
#   openssl s_client -connect csoh.org:443 -servername csoh.org </dev/null \
#     | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"
#   ->  DNS:*.csoh.org, DNS:csoh.org
#
# Under RFC 8659, once ANY issuewild record exists it takes over wildcard
# issuance completely and the issue records above no longer apply to wildcards.
# So an issuewild set that omitted letsencrypt.org would forbid the exact
# certificate this site runs on, and nothing would break until a renewal was
# silently refused weeks later. Keep this map identical to the issue map.
#
# (The other trap, `issuewild ";"` to deny wildcards outright, is the same
# mistake in a more obvious costume. Do not.)
resource "cloudflare_record" "caa_issuewild" {
  for_each = local.caa_authorized_cas

  zone_id = var.zone_id
  name    = var.zone_name
  type    = "CAA"
  ttl     = 3600

  data {
    flags = 0
    tag   = "issuewild"
    value = each.value
  }
}

# --- iodef: where a CA reports a request that violated the rules above.
# This is the alerting half of CAA. Without it a blocked mis-issuance attempt
# is silent, and an attempt is exactly the signal worth having.
resource "cloudflare_record" "caa_iodef" {
  zone_id = var.zone_id
  name    = var.zone_name
  type    = "CAA"
  ttl     = 3600

  data {
    flags = 0
    tag   = "iodef"
    value = "mailto:admin@csoh.org"
  }
}
