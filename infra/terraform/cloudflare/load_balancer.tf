# --------------------------------------------------------------------------
# This file builds the active/active multi-cloud load balancer at Cloudflare.
# Three building blocks, created in this order because each depends on the
# previous one:
#   1) a "monitor"      - the recurring health check that probes each origin
#   2) a "pool"         - the group of three cloud origins the monitor watches
#   3) a "load balancer"- the public hostname that hands traffic to the pool
# Plus one DNS record so "www.csoh.org" reaches the same place as the apex.
#
# Terraform vocabulary used throughout this file:
#   - A "resource" block tells Terraform to CREATE and manage a real object in
#     the cloud (here, things inside your Cloudflare account). Terraform will
#     create it if missing, update it to match this code, and delete it if you
#     remove the block. (A "data" source, not used here, only READS an existing
#     object without creating anything.)
#   - The two strings after `resource` are the TYPE and a local NAME you choose,
#     e.g. resource "cloudflare_load_balancer_monitor" "site" - the type comes
#     from the Cloudflare provider; "site" is just a label you reference later.
#   - `var.something` reads an input variable defined in variables.tf. Values
#     come from outside this code (the three cloud origin hostnames, the zone
#     IDs, etc.), so the same config works without hardcoding secrets/IDs.
#   - One resource can REFERENCE another by writing type.name.attribute, e.g.
#     cloudflare_load_balancer_monitor.site.id. Terraform reads that as "create
#     the monitor first, then plug its generated ID in here" - an implicit
#     dependency that orders the work for you (no manual depends_on needed).
# --------------------------------------------------------------------------

# Health monitor - Cloudflare probes each origin over HTTPS and pulls
# unhealthy origins out of rotation automatically. Because the three origins
# answer on different hostnames (cloudfront.net, run.app, web.core.windows.net)
# each pool origin sets its own Host header override below, which the monitor
# honors when probing.
resource "cloudflare_load_balancer_monitor" "site" {
  # Which Cloudflare account owns this monitor. Monitors and pools live at the
  # ACCOUNT level (not inside a single domain/zone), so they take account_id
  # rather than zone_id. Value comes from the account_id input variable.
  account_id = var.account_id
  # Probe each origin by making a real HTTPS request (the alternatives are
  # "http", "tcp", etc.). HTTPS is used so the check exercises the same
  # encrypted path real visitors use.
  type = "https"
  # HEAD, not GET. A GET made Cloudflare download the ENTIRE homepage from every
  # origin on every probe, and the probe runs from every Cloudflare data center
  # (see check_regions on the pool below) - roughly 1.09M probes per origin per
  # day. Azure Blob static websites cannot gzip, so each of those probes shipped
  # the full uncompressed index.html (52 KB, vs 11 KB gzipped): ~57 GB/day of
  # billed egress, ~$120/month, for bytes that were downloaded and discarded.
  # HEAD returns headers only (verified: Azure answers 200 with a 0-byte body),
  # so it still proves the origin is alive and serving 200s. Nothing is lost by
  # the switch because expected_body is not set, so the body was never inspected
  # in the first place. If you ever add expected_body, this must go back to GET.
  method = "HEAD"
  # The URL path to request on each origin. "/" is the site's home page, which
  # every origin serves, so it is a good "are you alive?" target.
  path = "/"
  # An origin is considered healthy only if it answers with HTTP 200 (OK).
  # Anything else (errors, redirects, timeouts) counts as a failed probe.
  expected_codes = "200"
  # How often to run the probe, in seconds, PER PROBE SOURCE. This is the single
  # biggest cost lever in the whole deployment, and it is not obvious why.
  #
  # The probe does not run once per interval - it runs once per interval from
  # every Cloudflare data center inside check_regions (see the pool below).
  # Measured from the billing data at interval=60: ~1.02M probes per origin per
  # day, i.e. ~711 distinct probe sources. On request-billed origins that is the
  # dominant workload. GCP Cloud Run charged 25.6M requests and 1.18M
  # CPU-seconds over 25 days - $47.64/month - while minimum-instance CPU came to
  # three cents, meaning the service genuinely scales to zero and simply never
  # gets the chance. Azure bills the same probes as read operations.
  #
  # 300 rather than 60 cuts that fan-out fivefold. The cost is detection
  # latency: an origin is marked down after `retries` consecutive failures, so
  # worst-case detection goes from interval*(1+retries) = 180s to 900s. With
  # three origins behind the load balancer that is the window in which a share
  # of requests can hit a dead origin, which is the trade being made here
  # deliberately - see the cost section of cloud-deployment.html.
  interval = 300
  # How many seconds to wait for a response before giving up on a single probe.
  timeout = 5
  # If a probe fails, retry this many times before declaring the origin down.
  # This avoids yanking an origin out of rotation over a single hiccup.
  retries = 2
  # Free-text label shown in the Cloudflare dashboard so humans know what this
  # monitor is for. Has no effect on behavior.
  description = "csoh.org origin health (HTTPS HEAD /)"
  # false = require a VALID TLS certificate from the origin during the probe.
  # We do NOT skip certificate verification, matching the strict TLS posture
  # set in zone.tf (every origin presents a real cert for its own hostname).
  allow_insecure = false
  # false = treat a redirect (3xx) as a failed health check rather than
  # following it. We expect "/" to return 200 directly; a redirect would mean
  # something is misconfigured, so it should mark the origin unhealthy.
  follow_redirects = false
}

# One pool holding all three origins. origin_steering "random" spreads live
# traffic across every healthy origin - this is the active/active behavior:
# AWS, GCP, and Azure all serve simultaneously, and any that fails its health
# check is skipped until it recovers.
#
# Each origin overrides the Host header to its own hostname. Without this,
# Cloudflare would forward Host: csoh.org and CloudFront / Cloud Run / Azure
# Blob would reject the request (they don't recognize that hostname).
resource "cloudflare_load_balancer_pool" "origins" {
  # Same account that owns the monitor above; pools are account-scoped too.
  account_id = var.account_id
  # Internal name for the pool, shown in the Cloudflare dashboard.
  name = "csoh-origins"
  # Human-readable note describing what is inside the pool.
  description = "AWS S3+CloudFront, GCP Cloud Run, Azure Blob static website"
  # Attach the health check defined above to this pool. We pass the monitor's
  # generated ID via cloudflare_load_balancer_monitor.site.id - this reference
  # is what makes Terraform create the monitor BEFORE the pool.
  monitor = cloudflare_load_balancer_monitor.site.id
  # Which Cloudflare regions run the health check. This attribute lives on the
  # POOL, not on the monitor (the v4 provider has no check_regions on
  # cloudflare_load_balancer_monitor at all - look for it there and you will not
  # find it).
  #
  # Leaving it unset means "probe from EVERY Cloudflare data center", which is
  # what we were doing: ~757 probe sources per 60s cycle, ~1.09M probes per
  # origin per day. Even as a HEAD that is ~33M billed storage transactions a
  # month on Azure (~$13). Three regions covering where the audience actually is
  # gives the same failure signal at a fraction of the probe volume.
  #
  # Region codes: WNAM/ENAM = Western/Eastern North America, WEU = Western
  # Europe. Full list:
  # https://developers.cloudflare.com/load-balancing/reference/region-mapping-api
  check_regions = ["ENAM", "WEU"]
  # The pool is considered "up" only while at least this many origins are
  # healthy. 1 means: as long as any single cloud is alive, keep serving. The
  # whole site stays online even if two of the three clouds go down.
  minimum_origins = 1
  # Where Cloudflare emails health-state-change alerts. Left empty = no email
  # notifications configured here.
  notification_email = ""

  # How traffic is distributed among the healthy origins IN this pool. This is
  # a nested configuration block (not its own resource), part of the pool.
  origin_steering {
    # "random" = send each request to a randomly chosen healthy origin. With
    # equal weights below, traffic spreads roughly evenly across AWS/GCP/Azure.
    # This is the core of the active/active design.
    policy = "random"
  }

  # Each `origins` block below defines ONE backend server (a real cloud origin)
  # that Cloudflare can forward visitor traffic to. Repeating the block adds
  # more origins to the same pool.

  # Origin 1: the AWS side (private S3 bucket fronted by a CloudFront CDN).
  origins {
    # Label for this origin in the dashboard / health UI.
    name = "aws-cloudfront"
    # The actual hostname Cloudflare connects to. Comes from the AWS Terraform
    # dir's CloudFront output, passed in via the aws_origin_host variable.
    address = var.aws_origin_host
    # true = this origin is in service and may receive traffic.
    enabled = true
    # Relative share of traffic vs the other origins. All three are weight 1,
    # so each gets an equal ~1/3 share when healthy.
    weight = 1
    # Rewrite an outgoing request header on the Cloudflare->origin hop. Needed
    # because CloudFront only answers for its OWN hostname, not "csoh.org".
    header {
      # The header to override...
      header = "Host"
      # ...set to this origin's real hostname so CloudFront accepts the request
      # (a list because a header can technically carry multiple values).
      values = [var.aws_origin_host]
    }
  }

  # Origin 2: the GCP side (nginx on Cloud Run, *.run.app).
  origins {
    name = "gcp-cloud-run"
    # Hostname from the GCP Terraform dir's Cloud Run URL output.
    address = var.gcp_origin_host
    enabled = true
    weight  = 1
    # Same Host-header trick: Cloud Run routes by the *.run.app hostname, so we
    # must send that as the Host header rather than "csoh.org".
    header {
      header = "Host"
      values = [var.gcp_origin_host]
    }
  }

  # Origin 3: the Azure side (Storage Account "static website" / $web blob host).
  origins {
    name = "azure-blob"
    # Hostname from the Azure Terraform dir's static-website output.
    address = var.azure_origin_host
    enabled = true
    weight  = 1
    # Same reasoning: the Azure blob endpoint serves its own *.web.core.windows
    # .net hostname, so override Host to match.
    header {
      header = "Host"
      values = [var.azure_origin_host]
    }
  }
}

# The Load Balancer itself, published at the apex. proxied=true keeps it
# behind Cloudflare's edge (cache + TLS + WAF). steering_policy "off" means
# "use the default pool" - and since all three origins live in that one pool,
# origin_steering above does the active/active distribution.
resource "cloudflare_load_balancer" "site" {
  # Unlike the monitor/pool, a load balancer is tied to a specific ZONE (the
  # csoh.org domain), so it takes zone_id rather than account_id.
  zone_id = var.zone_id
  # The hostname this LB answers on. var.zone_name defaults to "csoh.org", so
  # the load balancer IS the apex domain - visitors hitting csoh.org land here.
  name = var.zone_name
  # The pool(s) to use under normal conditions. This is a LIST (note the square
  # brackets), but we only need one pool since it already holds all three
  # origins. We reference the pool created above by its generated ID, which
  # also makes Terraform build the pool before this load balancer.
  default_pool_ids = [cloudflare_load_balancer_pool.origins.id]
  # The pool to fall back to if every default pool is unhealthy. We point it at
  # the same single pool - there is nothing else to fall back to, and this
  # field is required.
  fallback_pool_id = cloudflare_load_balancer_pool.origins.id
  # true = run this hostname THROUGH Cloudflare's network (orange-cloud), so it
  # gets edge caching, TLS termination, and the WAF. false would expose the
  # origins directly (DNS-only), which we do not want.
  proxied = true
  # "off" = don't do geo/dynamic steering between multiple pools; just use the
  # default pool. The active/active spread happens INSIDE the pool via the
  # origin_steering "random" setting above.
  steering_policy = "off"
  # Dashboard label for this load balancer.
  description = "csoh.org active/active multi-cloud edge LB"
}

# A cloudflare_record is a single DNS entry in the zone. This one makes
# "www.csoh.org" resolve to the same destination as the bare "csoh.org": it is
# a normal proxied CNAME that flattens onto the apex (the Load Balancer).
resource "cloudflare_record" "www" {
  # The zone (domain) this DNS record belongs to.
  zone_id = var.zone_id
  # The record's name within the zone. "www" expands to "www.csoh.org".
  name = "www"
  # A CNAME is an alias: "www" points at another name rather than an IP.
  type = "CNAME"
  # The target of the alias - the apex "csoh.org", i.e. the load balancer.
  # (Cloudflare "flattens" the CNAME so the apex resolves correctly.)
  content = var.zone_name
  # true = also send www through Cloudflare's edge, matching the apex so both
  # get caching/TLS/WAF and reach the same origins.
  proxied = true
  # TTL = how long resolvers may cache this record. Cloudflare requires it to
  # be "automatic" for proxied records, and the value 1 is how you select that.
  ttl = 1 # 1 = automatic (required when proxied)
}
