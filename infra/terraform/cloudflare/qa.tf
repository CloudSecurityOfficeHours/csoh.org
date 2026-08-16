# --- What this file does ---
# It publishes qa.csoh.org: a staging copy of the site that the `qa` branch
# deploys to, so a change can be looked at on a real origin before it is
# promoted to `main` and fanned out to all three production clouds.
#
# Three things have to be true for that hostname to work. Here: the DNS record,
# the Cloudflare Access login in front of it, and the Worker that rewrites the
# Host header (without it Cloud Run cannot tell which of its two services the
# request is for and answers 404). In rules.tf: a cache rule that stops the edge
# serving stale QA pages.
#
# WHAT THIS FILE DELIBERATELY DOES NOT DO. It does not add QA to the Load
# Balancer in load_balancer.tf. Pool members are health-checked from every
# Cloudflare data center - about 757 probe sources per cycle, ~1.09M probes per
# origin per day - which is the thing that turned a 52 KB index.html into a
# $119.77 Azure bandwidth bill in July 2026. A QA origin inside the pool would
# be probed around the clock, could never scale to zero, and would quietly cost
# more than production does. A plain proxied DNS record has none of that
# behaviour: nothing reaches the origin until a human loads the page.

# A single DNS record pointing qa.csoh.org at the QA Cloud Run service.
#
# It is a CNAME (an alias to another NAME rather than to an IP address) because
# Cloud Run publishes a hostname, not a stable address, and Google may change
# the address behind it at any time.
resource "cloudflare_record" "qa" {
  # The zone (domain) this record belongs to.
  zone_id = var.zone_id
  # The record's name within the zone: "qa" expands to qa.csoh.org.
  name = "qa"
  type = "CNAME"
  # The alias target: the *.run.app hostname of the csoh-site-qa service, fed
  # in from the gcp stack's `cloud_run_qa_service_url` output (see
  # variables.tf for the exact command).
  content = var.gcp_qa_origin_host
  # true = orange-cloud, i.e. route this hostname THROUGH Cloudflare's network.
  #
  # This is not the usual "so it gets caching and WAF" reason. It is load
  # bearing: Cloudflare Access below can only gate traffic that passes through
  # Cloudflare. Setting this to false (grey-cloud, DNS-only) would publish the
  # QA site to the open internet with no login at all, while every other part
  # of this file kept reporting success.
  proxied = true
  # Cloudflare requires "automatic" TTL on proxied records, and 1 is how that
  # is expressed.
  ttl = 1 # 1 = automatic (required when proxied)
}

# --- The login gate -----------------------------------------------------------
# Cloudflare Access sits in front of a hostname and refuses to pass a request to
# the origin until the visitor has proved who they are. It is part of Cloudflare
# Zero Trust, whose free tier covers up to 50 users - so this costs nothing at
# this size.
#
# WHY GATE QA AT ALL, given the content is only ever a few days ahead of a
# public site. Mainly to keep it out of search results. Every page carries an
# absolute <link rel="canonical"> and absolute og:url/JSON-LD pointing at
# csoh.org, so an indexable qa.csoh.org is a near-perfect duplicate of a site
# that is actively SEO-audited every week. A noindex header would be a request;
# a login page is a wall. It also means unreleased writing is not readable by
# anyone who guesses the hostname.
# (Resource naming note: the older `cloudflare_access_application` /
# `cloudflare_access_policy` names still work in provider v4 but are deprecated
# aliases, and the v4 provider warns on every plan. The
# `cloudflare_zero_trust_*` names below are the same objects under Cloudflare's
# current product naming, and are what the pending v5 upgrade expects - so
# writing them this way now avoids renaming these resources twice.)
resource "cloudflare_zero_trust_access_application" "qa" {
  # ACCOUNT-scoped, not zone-scoped, and this is worth knowing before you spend
  # an hour on it. Access applications can in principle be attached to either,
  # and attaching to the zone reads more naturally here because the app protects
  # exactly one hostname inside csoh.org. But Zero Trust is an account-level
  # product in current Cloudflare, and the zone-scoped Access API is legacy: a
  # token carrying Account -> Access: Apps and Policies can create this
  # resource, while the same token gets `Authentication error (10000)` on the
  # zone endpoint.
  #
  # That error is exactly the shape CLAUDE.md warns about - /user/tokens/verify
  # reports the token `active` regardless of scope, so an under-scoped or
  # wrong-endpoint call looks like a credential problem when it is neither. The
  # tell is that the same token succeeds on
  # /accounts/<id>/access/apps and fails on /zones/<id>/access/apps.
  #
  # Being account-scoped changes nothing about what is protected: `domain` below
  # names the hostname, and the account owns this zone.
  account_id = var.account_id
  # Label shown in the Zero Trust dashboard and on the login page itself.
  name = "csoh.org QA"
  # The hostname to protect. Must match the DNS record above; Access attaches
  # to the name, not to the origin behind it.
  domain = "qa.${var.zone_name}"
  # "self_hosted" = an ordinary web app behind Cloudflare, as opposed to SSH,
  # VNC, or a SaaS integration.
  type = "self_hosted"
  # How long a successful login lasts before the visitor is asked again. A day
  # is short enough to be a real gate and long enough not to interrupt an
  # afternoon of QA.
  session_duration = "24h"
  # Send visitors straight to the identity step instead of showing a chooser
  # page first. There is only one login method here (see the policy below), so
  # the chooser would be a pointless extra click.
  auto_redirect_to_identity = true
}

# An Access application on its own blocks EVERYONE - it is the policies attached
# to it that let specific people through. This is the only policy, so the rule
# is simply "these addresses, nobody else."
#
# No identity provider needs configuring for this to work. With none set up,
# Cloudflare offers its built-in One-Time PIN: the visitor types an email
# address, and if it is on the list below, Cloudflare emails a short code that
# logs them in. That is why this needs no Google/GitHub/Okta integration and no
# passwords stored anywhere.
resource "cloudflare_zero_trust_access_policy" "qa_allow_listed_emails" {
  # Which application this policy governs. Referencing the resource above also
  # tells Terraform to create the application first.
  application_id = cloudflare_zero_trust_access_application.qa.id
  # Policies must be scoped the same way as the application they govern, so this
  # is account-scoped too. Mixing the two produces the same 10000 error.
  account_id = var.account_id
  name       = "Allow listed emails"
  # Policies are evaluated in precedence order, lowest first. There is only one
  # here, so this is just "first".
  precedence = 1
  # What to do when the include block below matches: let the visitor in.
  # ("deny" and "bypass" are the other common decisions; bypass would skip the
  # login entirely and is exactly what this file must not do.)
  decision = "allow"

  # WHO matches. `include` is the "any of these" set - a visitor who satisfies
  # any entry is allowed. Listing individual email addresses is the tightest
  # option; `email_domain` would admit anyone at a domain, which is wrong for a
  # personal address, and Access also supports country, IP range, and identity
  # provider group matching.
  include {
    # Fed from var.qa_allowed_emails so the addresses stay out of this file -
    # everything under infra/ is published on the site as teaching material.
    email = var.qa_allowed_emails
  }
}

# --- The Host header rewrite ---------------------------------------------------
# Cloud Run decides WHICH service a request is for by reading the Host header,
# and this project now runs two of them. A proxied Cloudflare record forwards the
# ORIGINAL Host, so Cloud Run receives `Host: qa.csoh.org`, matches no service it
# knows, and answers 404 to everything - after DNS resolves, after TLS completes,
# and after Access has logged the visitor in, which makes it read like a broken
# deploy rather than a missing header.
#
# WHY A WORKER AND NOT AN ORIGIN RULE. An Origin Rule is the obvious tool and it
# is what this stack tried first. Host Header Override is a PAID-PLAN feature,
# though, and csoh.org is on the Free plan. The trap is the timing: the config
# validates, and `terraform plan` shows a clean create, because entitlement is
# only checked when the ruleset is actually written. The apply then fails with
# `not entitled to use the HostHeader override`. Plan success is not evidence
# that a Cloudflare feature is available to you.
#
# Production does not need any of this: its origins live in a Load Balancer pool
# and each pool origin sets its own host_header, which IS entitled because Load
# Balancing is a paid add-on. QA is deliberately outside that pool (see the cost
# note at the top of this file), so it needs its own mechanism.
#
# WHAT IT COSTS: nothing. Workers' free tier is 100,000 requests/day, and this
# runs only on qa.csoh.org, behind a login, for a handful of people.
#
# ORDERING NOTE: Access is evaluated BEFORE Workers, so this script never runs
# for an unauthenticated visitor. The login is not something this code has to
# enforce, or could accidentally bypass.
resource "cloudflare_workers_script" "qa_host_rewrite" {
  account_id = var.account_id
  name       = "csoh-qa-host-rewrite"
  # ES module syntax (`export default { fetch }`) rather than the older
  # addEventListener form, which Cloudflare is retiring.
  module = true

  # The whole proxy. Rebuild the URL with the origin's hostname and refetch;
  # `new Request(url, request)` carries the method, headers and body across
  # unchanged, and fetch derives the new Host from the URL.
  #
  # `redirect: "manual"` matters. Without it the Worker FOLLOWS any redirect the
  # origin issues and returns the final body, so a visitor who asks for a URL
  # that nginx redirects would silently receive different content at the address
  # they typed - and the redirect rules in nginx.conf would be untestable in QA,
  # which is one of the things QA exists to test. Manual passes the 3xx straight
  # back to the browser, which then follows it normally.
  content = <<-JS
    export default {
      async fetch(request) {
        const url = new URL(request.url);
        url.hostname = "${var.gcp_qa_origin_host}";
        return fetch(new Request(url, request), { redirect: "manual" });
      },
    };
  JS
}

# Bind the script to the hostname. The trailing /* is required: a route pattern
# without a path matches only the bare hostname, so the home page would proxy
# correctly and every asset under it would 404 - a failure that looks like a
# broken stylesheet rather than a routing mistake.
resource "cloudflare_workers_route" "qa" {
  zone_id     = var.zone_id
  pattern     = "qa.${var.zone_name}/*"
  script_name = cloudflare_workers_script.qa_host_rewrite.name
}
