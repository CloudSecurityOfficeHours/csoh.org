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
  #                the feedback loop: read it before tightening to reject.
  #                Neither address is a secret; both are published in public DNS
  #                by definition.
  #
  #                TWO destinations, comma-separated. Receivers send a copy to
  #                each, so this is additive and reversible - removing one does
  #                not disturb the other.
  #                  1. The Cloudflare DMARC Management address, which backs the
  #                     dashboard view under Email -> DMARC Management.
  #                  2. admin@csoh.org, which gets the RAW gzipped XML. The
  #                     dashboard summarises; the raw reports name the DKIM
  #                     SELECTOR each source signed with, which is what is
  #                     actually needed to identify the second signer on this
  #                     domain (default._domainkey, still unattributed) before
  #                     deciding on p=reject or on tightening SPF to -all.
  #
  #                WHY admin@csoh.org AND NOT A PERSONAL ADDRESS. RFC 7489
  #                section 7.1 requires External Destination Verification: when a
  #                rua mailbox sits at a DIFFERENT domain than the DMARC record,
  #                that other domain must publish
  #                    csoh.org._report._dmarc.<their-domain>  TXT  "v=DMARC1"
  #                to consent to receiving our reports. Checked before writing
  #                this: gmail.com publishes no such record for csoh.org and
  #                never will, so a personal Gmail address would be silently
  #                skipped by compliant receivers - reports simply would not
  #                arrive, with nothing to indicate why. The Cloudflare address
  #                above works precisely because Cloudflare DOES publish that
  #                record for its own domain (verify with
  #                `dig +short TXT csoh.org._report._dmarc.dmarc-reports.cloudflare.net`).
  #                admin@csoh.org is same-domain, so it needs no authorization
  #                at all. Any future third-party analyser (dmarcian, Postmark)
  #                hands you an address at THEIR domain for this same reason.
  #
  # Alignment mode is left at its default (relaxed) for both SPF and DKIM.
  # Strict alignment is a separate tightening and should not ride along with an
  # enforcement change - one variable at a time.
  # No surrounding quotes in this string. Cloudflare adds the TXT quoting itself
  # when it serves the record; embedding literal `"` here publishes them twice
  # and the policy stops parsing. Compare `dig +short TXT _dmarc.csoh.org`,
  # which shows the quotes Cloudflare added, against this value, which has none.
  content = "v=DMARC1; p=quarantine; sp=quarantine; pct=100; rua=mailto:325e7f2d0aeb4bf097745889b5b2dd23@dmarc-reports.cloudflare.net,mailto:admin@csoh.org"

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

# =============================================================================
# MTA-STS (RFC 8461) and TLS-RPT (RFC 8460)
# -----------------------------------------------------------------------------
# SPF, DKIM, and DMARC above are all about mail claiming to be FROM us. This
# block is about the other direction: mail arriving AT us, and whether it is
# encrypted in transit.
#
# SMTP between mail servers is opportunistic by default. The sending server
# connects in cleartext, reads the receiver's EHLO response, sees STARTTLS
# advertised, and upgrades. If STARTTLS is not advertised, it delivers in the
# clear anyway - that fallback is the entire design. An on-path attacker does
# not need to break TLS; it strips the STARTTLS capability out of the EHLO
# response, and the sender cheerfully hands over the message in plaintext.
# Nothing in SPF/DKIM/DMARC notices, because those authenticate the message,
# not the channel.
#
# MTA-STS closes that by letting the RECEIVING domain publish, out of band, a
# policy saying: TLS is mandatory, the certificate must be valid WebPKI and
# must match one of these MX hostnames. A sender that supports MTA-STS caches
# that policy and, on a stripped or mismatched handshake, FAILS the delivery
# (the message queues and the sender is told) instead of silently downgrading.
#
# This matters here for the same reason the DMARC block does: admin@csoh.org is
# the RFC 9116 `Contact:` in /.well-known/security.txt. Inbound vulnerability
# reports are precisely the mail least suited to being read off the wire.
#
# MTA-STS is a two-part mechanism, and BOTH parts have to be present:
#
#   1. A policy file at https://mta-sts.<domain>/.well-known/mta-sts.txt,
#      served as text/plain over HTTPS with a valid certificate. The HTTPS
#      requirement is what makes it trustworthy: DNS alone (pre-DNSSEC) could
#      be spoofed, so the policy is anchored in WebPKI instead.
#   2. A TXT record at _mta-sts.<domain> carrying an `id`. Senders poll the
#      cheap DNS record, and only re-fetch the expensive HTTPS policy when the
#      id changes.
#
# HOW THE POLICY IS HOSTED HERE
# -----------------------------------------------------------------------------
# The usual recipes reach for a Cloudflare Worker or a separate static bucket.
# Neither is needed: this site already serves /.well-known/ over HTTPS from
# three origins behind the edge, so `mta-sts` is just another proxied hostname
# pointed at the same place.
#
#   - The policy file is checked in at /.well-known/mta-sts.txt. That directory
#     is already in the published set (`+ /.well-known/**` in
#     tools/site-publish.filter) and `.well-known/**` is already a trigger path
#     in deploy.yml, so the file ships on the next deploy with no workflow
#     change. `.txt` already serves as text/plain there - verified against
#     /.well-known/security.txt, which RFC 9116 tooling fetches the same way.
#   - TLS is free: the Cloudflare Universal SSL certificate for this zone is a
#     WILDCARD (SANs *.csoh.org and csoh.org), so mta-sts.csoh.org is covered
#     the moment the record exists. No new issuance, and therefore nothing to
#     change in dns_caa.tf.
#   - The www -> apex redirect in rules.tf does NOT catch this hostname. Its
#     expression is an exact match, `http.host eq "www.csoh.org"`, not a suffix
#     or wildcard test, so mta-sts.csoh.org is unaffected. Worth stating
#     because a redirect here would be a silent breakage: senders would fetch
#     the policy, follow the 301, and RFC 8461 section 3.3 requires them to
#     REFUSE a policy fetch that redirects. The policy would simply stop
#     existing, with no error anywhere on our side.
#
# Because the policy file rides the site deploy and the records below ride
# Terraform, the two halves land at different times. Order matters: apply the
# CNAME and publish the policy file FIRST, confirm it fetches, and only then
# let the _mta-sts TXT record advertise it. A TXT record pointing at a policy
# that 404s is not a failure a sender reports usefully.
# =============================================================================

# The hostname that serves the policy. A proxied CNAME onto the apex, written
# exactly like cloudflare_record.www in load_balancer.tf - same target, same
# proxied/ttl pair - because it is the same thing: another name for the load
# balancer, so the policy is served from all three origins rather than one.
resource "cloudflare_record" "mta_sts" {
  zone_id = var.zone_id
  # `mta-sts` expands to mta-sts.csoh.org. The name is fixed by RFC 8461
  # section 3.1; it is not a label we get to choose.
  name = "mta-sts"
  type = "CNAME"
  # The apex, i.e. the load balancer. Cloudflare flattens the CNAME.
  content = var.zone_name
  # true = through Cloudflare's edge, so this hostname gets the same TLS
  # termination and the wildcard certificate the rest of the site gets. A
  # DNS-only record here would expose an origin directly AND would not present
  # a certificate valid for mta-sts.csoh.org, which fails the policy fetch.
  proxied = true
  ttl     = 1 # 1 = automatic (required when proxied)
}

# The DNS half of MTA-STS: tells senders a policy exists, and gives them a
# cheap way to notice it changed.
resource "cloudflare_record" "mta_sts_id" {
  zone_id = var.zone_id
  # `_mta-sts` expands to _mta-sts.csoh.org. Underscore-prefixed service name,
  # like _dmarc above - nothing resolves it as a host.
  name = "_mta-sts"
  type = "TXT"

  # v=STSv1  the version tag; required, and required to come first.
  #
  # id=      an opaque string, max 32 alphanumeric characters. It carries no
  #          meaning to a sender - it is purely a change detector. A sender
  #          caches the policy for up to max_age (7 days, below) and re-reads
  #          this TXT record cheaply; when the id differs from the cached one,
  #          it re-fetches the policy over HTTPS.
  #
  # THE RULE, and the only real footgun in this file: change this id EVERY time
  # /.well-known/mta-sts.txt changes, in the same commit. Forget it and senders
  # keep enforcing the OLD policy from cache for up to max_age. Add an MX host
  # without bumping the id and mail to that new host fails for a week; move
  # from testing to enforce without bumping it and the change simply does not
  # take effect, which is worse than it sounds because it looks like it did.
  #
  # The format is a convention, not a spec requirement: YYYYMMDDNN, the date of
  # the policy change plus a two-digit counter for multiple changes in one day.
  # Date-based ids sort, are obviously stale at a glance, and cannot collide
  # with a previous value the way a hand-picked "v2" can.
  #
  #   20260726  01  <- initial policy, mode: testing
  #
  # No surrounding quotes in this string, for the same reason as the DMARC
  # record above: Cloudflare adds TXT quoting when it serves the record, and
  # embedding literal `"` here publishes them twice and breaks parsing.
  content = "v=STSv1; id=2026072601"

  # Policy data, not a host - nothing to proxy.
  proxied = false
  # 1 hour, matching _dmarc. Senders re-check this record often; a short TTL
  # is what makes an id bump take effect promptly.
  ttl = 3600
}

# TLS-RPT (RFC 8460): where receivers should send reports about TLS failures
# when delivering to us.
#
# This is the instrument panel for everything above, and it is the reason the
# policy starts in `testing` mode rather than `enforce`. Without it, a broken
# MTA-STS policy is invisible from our side: the sender's queue fills up, the
# sender's postmaster sees the errors, and we see silence. With it, we get
# daily JSON summaries naming which sending domains failed, against which MX
# host, and why (certificate mismatch, STARTTLS unavailable, validation error).
#
# TLS-RPT is independent of MTA-STS and of DMARC - it reports transport
# failures, not authentication failures - but it is the same feedback-loop
# pattern as the `rua=` in the DMARC record above: publish the weak setting,
# read the reports, tighten once they are clean.
resource "cloudflare_record" "smtp_tls_reporting" {
  zone_id = var.zone_id
  # `_smtp._tls` expands to _smtp._tls.csoh.org, fixed by RFC 8460 section 3.
  name = "_smtp._tls"
  type = "TXT"

  # v=TLSRPTv1  version tag; required first.
  # rua=        where to send the aggregate reports. admin@csoh.org is the same
  #             mailbox as the security.txt Contact, which is deliberate: the
  #             person who cares that vulnerability reports arrive encrypted is
  #             the person who should see it when they do not.
  #
  # Reports are sent by mail here. That is mildly circular - if inbound mail is
  # badly broken the reports may not arrive either - but the failure mode this
  # guards against (a subset of senders failing TLS) still delivers reports
  # from everyone else. An https:// rua endpoint is the alternative if that
  # ever becomes a real concern.
  content = "v=TLSRPTv1; rua=mailto:admin@csoh.org"

  proxied = false
  ttl     = 3600
}

# -----------------------------------------------------------------------------
# MOVING FROM `testing` TO `enforce`
# -----------------------------------------------------------------------------
# /.well-known/mta-sts.txt ships with `mode: testing` on purpose. In testing
# mode a sender evaluates the policy, reports any failure via TLS-RPT, and then
# delivers the message anyway. In `enforce` mode the same failure means the
# message is not delivered. That is the whole point of MTA-STS, and also why
# it is not the starting position: a wrong MX hostname, a typo, an expired
# certificate on the policy host, or a 404 on the policy file blackholes
# inbound mail - including the vulnerability reports this is meant to protect.
# Testing mode gives the same visibility with none of that risk.
#
# The checklist before flipping it:
#
#   1. Confirm the policy actually serves:
#        curl -sI https://mta-sts.csoh.org/.well-known/mta-sts.txt
#      Want `200` and `content-type: text/plain`, with NO redirect.
#   2. Confirm the TXT records are live:
#        dig +short TXT _mta-sts.csoh.org
#        dig +short TXT _smtp._tls.csoh.org
#   3. Confirm the mx: lines still match reality. They are Google Workspace's
#      five hosts, verified against `dig +short MX csoh.org`:
#        aspmx.l.google.com and alt1-4.aspmx.l.google.com
#      MTA-STS matches on the certificate's identity, so this list has to track
#      any MX change. If the MX records ever move, the policy file and the id
#      below must change in the SAME commit as the DNS change, not after it.
#   4. Let TLS-RPT run for at least one full max_age window (7 days, and
#      realistically two) and read the reports. Zero failures from real senders
#      is the bar. A large sender like Google reporting success at volume is
#      the useful signal; silence is not.
#   5. Then, in one commit: edit `mode: testing` -> `mode: enforce` in
#      /.well-known/mta-sts.txt AND bump the id in cloudflare_record.mta_sts_id
#      (e.g. to 2026080201). Deploy the file first, apply the DNS after.
#
# max_age is 604800 (7 days). It is the sender-side cache lifetime, and it cuts
# both ways: long enough that a transient outage of this site does not drop the
# policy, but also the window during which a BAD enforce-mode policy stays
# pinned in senders' caches after we have fixed it. Seven days is the common
# production value and is fine in testing mode. There is no way to shorten that
# window retroactively, which is the strongest argument for step 4 above.
#
# Note the split ownership one more time, because it is easy to half-ship:
# .well-known/mta-sts.txt reaches production via a normal deploy (`.well-known/**`
# is already in deploy.yml's paths filter, so a commit touching only that file
# does trigger one). The three records here need `terraform apply` in
# infra/terraform/cloudflare/. Neither half does anything useful alone.
