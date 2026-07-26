# =============================================================================
# CAA - which certificate authorities may issue for csoh.org
# -----------------------------------------------------------------------------
# A CAA record (RFC 8659) is the only mechanism that constrains WHICH CAs are
# allowed to issue a certificate for a domain. With no CAA record at all - the
# state before this file existed - every publicly trusted CA on earth, roughly
# fifty of them, is permitted. Any one of them mis-issuing, or being tricked by
# a transient DNS or BGP hijack during domain validation, produces a valid
# certificate for csoh.org that browsers accept.
#
# HSTS preload does not help with this. A preloaded domain still trusts any
# publicly trusted chain; it only forces HTTPS, it does not say whose HTTPS.
#
# What this cannot do: CAA is checked by the CA at issuance time, not by
# browsers. It is a control on the issuance process, so it depends on CAs
# honouring it (they are required to) and on the DNS answer being genuine -
# which is an argument for enabling DNSSEC, still outstanding.
# =============================================================================

# -----------------------------------------------------------------------------
# CHOOSING THE CA LIST - read before narrowing it
# -----------------------------------------------------------------------------
# The temptation is to pin only the CA currently in use. That breaks the site.
#
# csoh.org is served by Cloudflare Universal SSL, and Cloudflare chooses the
# issuing CA itself and rotates between them without notice. On the Free plan
# there is no setting to fix it to one CA (that is an Advanced Certificate
# Manager feature). The certificate live at the time of writing was issued by
# Let's Encrypt and expires 2026-09-29, so a renewal is due around late August.
# If that renewal picks a CA this list omits, issuance is refused, and the
# failure is quiet until the existing certificate simply expires.
#
# So the list below is deliberately broader than a minimal pin: it covers the
# CAs Cloudflare draws on for Universal SSL. That is still a reduction from
# ~50 possible issuers to 3, which is where nearly all of the security benefit
# of CAA actually comes from.
#
# NARROW THIS ONLY IF you move to Advanced Certificate Manager and select the
# CA explicitly - and ADD to it, before switching, if you ever provision a
# certificate from a CA not listed here.

# --- Let's Encrypt: the issuer of the certificate currently being served.
resource "cloudflare_record" "caa_letsencrypt" {
  zone_id = var.zone_id
  name    = var.zone_name
  type    = "CAA"
  ttl     = 3600
  data {
    # flags=0 means "not critical": a CA that does not understand this record
    # may proceed rather than refusing outright. 0 is the normal value.
    flags = 0
    # "issue" authorises this CA to issue certificates for this domain.
    tag   = "issue"
    value = "letsencrypt.org"
  }
}

# --- Google Trust Services: Cloudflare's other primary Universal SSL CA.
resource "cloudflare_record" "caa_google" {
  zone_id = var.zone_id
  name    = var.zone_name
  type    = "CAA"
  ttl     = 3600
  data {
    flags = 0
    tag   = "issue"
    value = "pki.goog"
  }
}

# --- SSL.com: also in Cloudflare's rotation. Present as headroom so a rotation
# cannot fail issuance; remove it only if you have pinned the CA elsewhere.
resource "cloudflare_record" "caa_sslcom" {
  zone_id = var.zone_id
  name    = var.zone_name
  type    = "CAA"
  ttl     = 3600
  data {
    flags = 0
    tag   = "issue"
    value = "ssl.com"
  }
}

# -----------------------------------------------------------------------------
# THERE IS DELIBERATELY NO issuewild RECORD HERE
# -----------------------------------------------------------------------------
# The obvious-looking hardening is `issuewild ";"`, which denies all wildcard
# issuance on the grounds that nothing needs one. On this domain that would
# have broken certificate renewal outright.
#
# Cloudflare Universal SSL issues a WILDCARD certificate. Verified against the
# live endpoint:
#
#   openssl s_client -connect csoh.org:443 -servername csoh.org </dev/null \
#     | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"
#   ->  DNS:*.csoh.org, DNS:csoh.org
#
# Under RFC 8659, when no `issuewild` record is present the `issue` records
# above govern wildcard issuance as well. Omitting it is therefore both correct
# and the safe default: the same three CAs are authorised, for wildcard and
# non-wildcard alike. Adding `issuewild ";"` would forbid the very certificate
# the site depends on, and the failure would not surface until a renewal was
# refused weeks later.
#
# If you ever DO add an issuewild record, it must list these same CAs.

# --- iodef: where a CA should report a request that violates the rules above.
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
