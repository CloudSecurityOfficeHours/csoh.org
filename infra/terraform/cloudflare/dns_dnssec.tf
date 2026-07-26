# =============================================================================
# DNSSEC - cryptographically sign the csoh.org zone
# =============================================================================
# DNS answers are unauthenticated by default: a resolver has no way to tell a
# genuine answer from one injected by an on-path attacker or a poisoned cache.
# DNSSEC fixes that by having the zone owner sign every record set, and by
# having the parent zone (.org) publish a DS record that vouches for the
# signing key. A validating resolver then refuses forged answers outright.
#
# WHAT THIS ACTUALLY PROTECTS HERE, which is narrower than it first appears.
# The website is already well covered without DNSSEC: csoh.org is on the HSTS
# preload list, so browsers refuse plaintext and a forged A record still cannot
# produce a certificate a browser will accept. The records with no equivalent
# transport-layer backstop are the ones worth signing:
#
#   * MX          - forge these and inbound mail goes to an attacker's server.
#   * SPF / DKIM / DMARC TXT - forge a permissive policy and a receiver
#     validating a spoofed message sees a pass. This directly undermines the
#     DMARC enforcement in dns_mail.tf, which is only as trustworthy as the
#     DNS answer carrying it.
#   * CAA         - see dns_caa.tf. A CA checks CAA at issuance over plain DNS;
#     an attacker who can forge that answer can strip the restriction and get a
#     certificate from a CA the real records exclude.
#   * _acme-challenge TXT - forge it and satisfy a CA's DNS-01 validation
#     directly, minting a certificate for the domain.
#
# So DNSSEC is what makes the other two DNS controls in this directory mean
# something. On its own each is a record an attacker on the DNS path could
# simply replace.
# =============================================================================

# THE USUAL RISK DOES NOT APPLY HERE, AND IT IS WORTH KNOWING WHY.
#
# The classic way to take a domain offline is a DNSSEC mismatch: the registrar
# publishes a DS record pointing at a signing key the DNS provider is no longer
# using, so every validating resolver concludes the answers are forged and
# refuses them. The domain does not degrade, it disappears - and only for the
# subset of users behind validating resolvers, which makes it maddening to
# diagnose.
#
# That failure needs the registrar and the DNS provider to disagree. For
# csoh.org they are the same company: `whois csoh.org` reports
# "Registrar: Cloudflare, Inc." and the nameservers are rosalie/yahir.ns.
# cloudflare.com. Cloudflare therefore adds the DS record at .org itself when
# signing is enabled, and removes it if signing is ever turned off. There is no
# copy-paste step to get wrong and no second system to drift from.
#
# IF THE DOMAIN IS EVER TRANSFERRED to another registrar, this stops being
# true. Disable DNSSEC BEFORE the transfer and re-enable it after, or the new
# registrar inherits a DS record for a key that no longer signs the zone.
resource "cloudflare_zone_dnssec" "site" {
  zone_id = var.zone_id

  lifecycle {
    # Deleting this resource disables zone signing. With Cloudflare as
    # registrar it should also withdraw the DS record, but the window between
    # those two operations is precisely the mismatch described above, and the
    # blast radius is "the domain stops resolving for anyone whose resolver
    # validates". Nothing here is worth that, so make it impossible to remove
    # by accident - a `terraform destroy` or a stray resource deletion now
    # fails loudly instead. Removing DNSSEC deliberately means deleting this
    # block first, which is the point.
    prevent_destroy = true
  }
}
