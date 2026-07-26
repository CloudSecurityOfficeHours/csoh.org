# =============================================================================
# Mail authentication DNS - DMARC
# -----------------------------------------------------------------------------
# csoh.org sends mail (Google Workspace, plus the Kit newsletter) and, more to
# the point, receives it: admin@csoh.org is the RFC 9116 `Contact:` in
# /.well-known/security.txt, so it is the address a stranger uses to report a
# vulnerability. That makes "can someone send mail that looks like it came from
# us" a real question rather than a hygiene checkbox.
#
# SPF and DKIM answer "is this message authentic". DMARC is the third leg: it
# publishes what a receiving server should DO when the answer is no, and asks
# for reports about attempts. Without it, SPF and DKIM are advisory.
#
# This record lives in Terraform rather than the dashboard for the same reason
# the rest of this stack does: an unmanaged control drifts silently, and nobody
# notices a weakened mail policy until it is used against them.
# =============================================================================

# A DNS TXT record at the special name `_dmarc.<domain>`, which is where every
# receiving mail server looks for the domain's DMARC policy.
resource "cloudflare_record" "dmarc" {
  zone_id = var.zone_id
  # `_dmarc` expands to _dmarc.csoh.org. The leading underscore marks it as a
  # service record rather than a hostname; nothing resolves it as a host.
  name = "_dmarc"
  type = "TXT"

  # The policy itself. Reading it left to right:
  #
  #   v=DMARC1     the version tag; required, and required to come first.
  #
  #   p=quarantine what to do with mail claiming to be from csoh.org that fails
  #                BOTH SPF and DKIM alignment: treat it as suspicious (spam
  #                folder) rather than deliver it normally.
  #
  #                This was `p=none` until 2026-07-25. `none` means "take no
  #                action, deliver it anyway, just tell me about it" - a
  #                monitoring mode intended to be temporary while you confirm
  #                your legitimate senders pass. Left in place permanently, as
  #                it was here, it means SPF and DKIM are published correctly
  #                and then explicitly ignored by every receiver: anyone could
  #                send mail as admin@csoh.org and it would land in inboxes.
  #
  #                Deliberately NOT `p=reject` yet. Quarantine is recoverable -
  #                a false positive lands in a spam folder where the recipient
  #                can still find it, whereas reject destroys the message. Move
  #                to reject once the aggregate reports below show a clean
  #                period with no legitimate sender failing.
  #
  #   sp=quarantine the same policy for SUBDOMAINS. Without this, subdomains
  #                inherit `p`, but stating it explicitly means a future
  #                subdomain cannot silently become a weaker spoofing target.
  #
  #   pct=100      apply the policy to all failing mail. (100 is the default;
  #                written out because a lower value is the standard way to ramp
  #                enforcement, and an unstated default reads like an oversight.)
  #
  #   rua=         where to send aggregate reports - daily XML summaries of who
  #                sent mail as csoh.org and whether it authenticated. This is
  #                the Cloudflare DMARC Management address that was already
  #                configured, kept as-is. It is the feedback loop: read it
  #                before tightening to reject. Not a secret; it is published in
  #                public DNS by definition.
  #
  # Alignment mode is left at its default (relaxed) for both SPF and DKIM.
  # Strict alignment is a separate tightening and should not ride along with an
  # enforcement change - one variable at a time.
  # No surrounding quotes in this string. Cloudflare adds the TXT quoting itself
  # when it serves the record; embedding literal `"` here publishes them twice
  # and the policy stops parsing. Compare `dig +short TXT _dmarc.csoh.org`,
  # which shows the quotes Cloudflare added, against this value, which has none.
  content = "v=DMARC1; p=quarantine; sp=quarantine; pct=100; rua=mailto:325e7f2d0aeb4bf097745889b5b2dd23@dmarc-reports.cloudflare.net"

  # A DMARC record is policy data, not a host - there is nothing to proxy.
  proxied = false
  # 1 hour. Short enough to back a change out quickly if the reports show a
  # legitimate sender failing, long enough not to hammer resolvers.
  ttl = 3600
}

# -----------------------------------------------------------------------------
# WHY THERE IS NO SPF RESOURCE HERE (yet)
# -----------------------------------------------------------------------------
# The apex SPF record is currently `v=spf1 include:_spf.google.com ~all`. The
# `~all` is a SOFT fail: "mail from anywhere else is probably not us, but do not
# reject it". The hard version is `-all`.
#
# Tightening it is deliberately NOT bundled with the DMARC change above, because
# the two have different risk profiles here. Two DKIM selectors are published on
# this domain - `google` (Google Workspace) and `default` - which means a second
# sender is set up to sign as csoh.org. DMARC passes if EITHER SPF or DKIM
# aligns, so that sender survives the change above on its DKIM signature alone.
# It would not necessarily survive `-all`, because some receivers weight an SPF
# hard fail heavily on its own, independently of DMARC.
#
# So: confirm from the aggregate reports which senders are actually in use and
# that each one's DKIM aligns, and only then decide about `-all`. If the second
# sender turns out to be the Kit newsletter, the correct fix is to add its SPF
# include (and confirm its DKIM), not to leave `~all` forever.
