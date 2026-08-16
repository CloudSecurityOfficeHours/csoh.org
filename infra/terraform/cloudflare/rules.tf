# =============================================================================
# Response security headers - the edge equivalent of nginx-security-headers.conf
# -----------------------------------------------------------------------------
# Set once at Cloudflare, applied to every response regardless of which origin
# served it. This is the single source of truth for the site's security
# headers; keep the values in sync with nginx-security-headers.conf.
# =============================================================================
# A "resource" block tells Terraform to CREATE and manage a real object in a
# cloud provider. The two quoted strings are the resource TYPE
# ("cloudflare_ruleset", defined by the Cloudflare provider) and a local NAME
# ("security_headers") we choose to refer to it elsewhere in this Terraform code.
# A "ruleset" is Cloudflare's ordered list of rules that run on traffic at a
# specific point in request/response handling (the "phase", set below).
resource "cloudflare_ruleset" "security_headers" {
  # "var.zone_id" reads the input variable named zone_id (declared in
  # variables.tf). A Cloudflare "zone" is one domain (csoh.org) and all its
  # settings; this ID says which domain this ruleset attaches to.
  zone_id = var.zone_id
  # Human-friendly name + description shown in the Cloudflare dashboard.
  name        = "csoh-security-headers"
  description = "Baseline security headers on every response (mirrors nginx-security-headers.conf)"
  # "zone" = this ruleset applies to the whole zone (the entire domain).
  kind = "zone"
  # The phase decides WHEN these rules run. This phase rewrites/adds headers on
  # the RESPONSE leaving Cloudflare, just before it reaches the visitor's browser.
  phase = "http_response_headers_transform"

  # A "rules" block is one rule inside the ruleset. A ruleset can hold several;
  # this one holds a single rule that fires on every response.
  rules {
    # "ref" is a stable internal handle for this rule (used by Cloudflare to
    # track it across updates). "description" is the dashboard label.
    ref         = "set_security_headers"
    description = "Set HSTS, CSP, and the rest on all responses"
    # "expression" is Cloudflare's rule language deciding which requests match.
    # "true" means "match everything" - these headers go on every response.
    expression = "true"
    # "rewrite" is the action for the headers phase: add/replace response headers.
    action = "rewrite"
    # The rule is live. Set false to keep it defined but turned off.
    enabled = true

    # "action_parameters" carries the details of what the action does - here, the
    # exact headers to set. Each "headers" block sets one response header.
    action_parameters {
      # Each header block has: "name" (the HTTP header), "operation" ("set"
      # means create-or-overwrite), and "value" (what to set it to).
      # HSTS: tells browsers to ONLY ever reach this site over HTTPS, for the
      # next year (max-age in seconds), including subdomains; "preload" opts into
      # browsers' built-in HTTPS-only lists.
      headers {
        name      = "Strict-Transport-Security"
        operation = "set"
        value     = "max-age=31536000; includeSubDomains; preload"
      }
      # "nosniff" stops browsers from guessing a file's type and running, say, a
      # text file as JavaScript - a common attack vector.
      headers {
        name      = "X-Content-Type-Options"
        operation = "set"
        value     = "nosniff"
      }
      # "DENY" forbids any other site from embedding this one in an <iframe>,
      # blocking clickjacking. (frame-ancestors in the CSP below does the same in
      # the modern way; this covers older browsers.)
      headers {
        name      = "X-Frame-Options"
        operation = "set"
        value     = "DENY"
      }
      # Controls how much of the current URL is sent as the "Referer" when users
      # click away: full URL to same-origin links, only the origin to other sites.
      headers {
        name      = "Referrer-Policy"
        operation = "set"
        value     = "strict-origin-when-cross-origin"
      }
      # Disables browser features the site never uses (camera, mic, location,
      # etc.). Empty "()" means "allow for no one", shrinking the attack surface.
      headers {
        name      = "Permissions-Policy"
        operation = "set"
        value     = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()"
      }
      # Content-Security-Policy (CSP): a strict allowlist of where the page may
      # load each kind of resource from. "'self'" = only this domain. Scripts,
      # styles, fonts, and network calls are locked to 'self'; images also allow
      # YouTube thumbnails + inline "data:" URIs; iframes from YouTube, the
      # Wayback Machine, and Google Docs/Drive (embedded presentation decks on
      # presentations.html); "frame-ancestors 'none'" blocks embedding; and
      # "object-src 'none'" bans plugins like Flash. This is the strongest single
      # defense against cross-site scripting (XSS).
      #
      # NOTE: the lifecycle block below sets ignore_changes = [rules], so editing
      # this CSP value does NOT reach the edge on `terraform apply`. To actually
      # allow the GoatCounter origin (csoh.goatcounter.com, added to img-src +
      # connect-src for cookieless analytics), update the CSP in the Cloudflare
      # dashboard, or temporarily drop ignore_changes for one apply. Otherwise
      # /vendor/goatcounter-count.js loads fine but the analytics beacon is
      # silently CSP-blocked and no hits are recorded.
      headers {
        name      = "Content-Security-Policy"
        operation = "set"
        value     = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://csoh.org https://img.youtube.com https://i.ytimg.com https://csoh.goatcounter.com data:; font-src 'self'; connect-src 'self' https://csoh.goatcounter.com; frame-src https://www.youtube.com https://web.archive.org https://docs.google.com https://drive.google.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
      }
      # COOP: isolates this site into its own browser process group so other
      # windows/tabs it opens (or that open it) can't share memory with it.
      headers {
        name      = "Cross-Origin-Opener-Policy"
        operation = "set"
        value     = "same-origin"
      }
      # CORP: tells browsers other sites may NOT load this site's resources
      # cross-origin, mitigating side-channel data leaks.
      headers {
        name      = "Cross-Origin-Resource-Policy"
        operation = "set"
        value     = "same-origin"
      }
    }
  }

  # A "lifecycle" block tunes how Terraform manages this resource.
  # "ignore_changes" lists attributes Terraform should STOP comparing against the
  # live cloud state - so differences there won't trigger an update. Here it is a
  # deliberate workaround for a provider bug (explained just below):
  lifecycle {
    # The cloudflare v4 provider returns this rule's multi-header block in a
    # non-deterministic order, causing a perpetual "Provider produced inconsistent
    # result after apply" on re-apply. The headers ARE applied correctly at the edge
    # (verified via curl); ignore rule drift so `terraform apply` stays clean.
    # Revisit when upgrading to the cloudflare v5 provider, which fixes the ordering.
    #
    # KNOW WHAT THIS COSTS: `rules` is the only meaningful attribute of a
    # cloudflare_ruleset, so ignoring it makes this resource inert after
    # creation. Editing any header value above and running `terraform apply`
    # gives a clean plan and changes NOTHING at the edge. That matters more
    # here than it looks, because this ruleset is the only source of these
    # headers for the Azure origin - Azure Blob static websites cannot set
    # response headers at all. The GCP/nginx origin sets them independently via
    # nginx-security-headers.conf, and the AWS origin does too via
    # aws_cloudfront_response_headers_policy.security in aws/cloudfront.tf,
    # but only once that config is applied - until then AWS depends on the edge
    # as well. Keep all three copies of the values in step.
    #
    # Because Terraform cannot enforce this, CI asserts it from the outside
    # instead: tools/check_edge_headers.py parses the header values out of THIS
    # file and compares them against what csoh.org actually serves, and the
    # purge-cloudflare job in deploy.yml fails the deploy on any drift. So an
    # edit here still gets caught - it just has to be applied by hand in the
    # Cloudflare dashboard (or by dropping this block for one apply) first.
    ignore_changes = [rules]
  }
}

# =============================================================================
# Legacy redirects - the edge equivalent of the .htaccess RewriteRules
# -----------------------------------------------------------------------------
# The /csoh/* prefix strip and the bare /index.php redirect. Rules evaluate
# top-to-bottom; redirect is terminating. Verify with curl after apply (see the
# cutover runbook in infra/README.md).
# =============================================================================
# A second ruleset, this time in the request-redirect phase. These rules look at
# the INCOMING request and send the browser a redirect before any origin is hit.
resource "cloudflare_ruleset" "redirects" {
  zone_id     = var.zone_id
  name        = "csoh-legacy-redirects"
  description = "301 redirects for the /csoh/ prefix and bare /index.php"
  kind        = "zone"
  # This phase runs early on the REQUEST and can issue redirects whose target is
  # computed from the request (hence "dynamic"), e.g. preserving the path.
  phase = "http_request_dynamic_redirect"

  # --- www.* -> apex (strip the www. label, preserve path + query) ---
  # Rules are evaluated top-to-bottom; a redirect is "terminating" (it ends
  # processing and replies immediately), so order matters.
  rules {
    ref         = "www_to_apex"
    description = "www.csoh.org/* -> csoh.org/*"
    # Match only requests whose Host header is exactly www.csoh.org. In this
    # expression language "eq" means equals; the \" are escaped double-quotes
    # because the whole expression is itself a double-quoted string.
    expression = "http.host eq \"www.csoh.org\""
    action     = "redirect"
    enabled    = true
    action_parameters {
      # "from_value" describes a redirect whose destination is built dynamically.
      from_value {
        # HTTP 301 = permanent redirect (browsers/search engines remember it).
        status_code = 301
        # Keep any "?query=string" when redirecting.
        preserve_query_string = true
        # The destination URL, computed by an expression rather than hardcoded.
        target_url {
          # Build the destination from the PATH only, and hardcode the scheme
          # and host. Never derive it from the request's own scheme.
          #
          # This used to be:
          #   wildcard_replace(http.request.full_uri, "https://www.*", "https://$${1}")
          # which was an infinite redirect loop on plaintext HTTP. The rule's
          # expression (`http.host eq "www.csoh.org"`) matches http:// requests
          # too, and this dynamic-redirect phase runs BEFORE "Always Use HTTPS"
          # (zone.tf). On an http:// request the full_uri is
          # "http://www.csoh.org/..." , the "https://www.*" pattern does not
          # match, wildcard_replace returns the input unchanged, and Cloudflare
          # 301s the request to itself - forever, in cleartext, so the browser
          # never reaches a response that could carry the HSTS header.
          # Verified live before the fix: `curl -I http://www.csoh.org/about.html`
          # returned `Location: http://www.csoh.org/about.html`.
          #
          # preserve_query_string above carries any "?query=string".
          expression = "concat(\"https://csoh.org\", http.request.uri.path)"
        }
      }
    }
  }

  # --- RETIRED 2026-08-09: csoh_prefix_strip (/csoh/* -> /*) ---
  # This dynamically stripped a "/csoh/" prefix, a layout two site generations
  # old. It was removed to free a slot: this phase is capped at 10 rules on the
  # Free plan, and Cloudflare rejects the entire ruleset update at 11 with
  # "exceeded the maximum number of rules in the phase
  # http_request_dynamic_redirect: N out of 10 (50001)" - an atomic failure, so
  # you find out at apply, not at plan.
  #
  # The evidence it was dead weight: Search Console's complete "Not found (404)"
  # export of 2026-08-09 held 224 URLs and not one was /csoh/*, and the whole
  # property reported a single "Page with redirect". Google had no memory of
  # that prefix at all.
  #
  # If /csoh/... links ever resurface, do not re-add this here - the phase is
  # now full. Put them in a Bulk Redirect list instead (account-scoped, its own
  # quota); that also needs Account -> Filter Lists + Rulesets on the token,
  # which the current zone-scoped one does not have.

  # The old PHP front-controller URLs, merged into conc8_root below - both send
  # traffic to the bare home page with identical parameters, so they do not
  # need separate rules.

  # --- Retired career pages -> consolidated guide ---
  # Three entry-path pages were merged into breaking-into-cloud-security.html
  # in commit dda6a39b (2026-07-20) and the source files deleted. The 301s were
  # written into .htaccess, which nothing in this stack reads, so all three
  # 404'd in production from the day they were removed - long enough for Google
  # Search Console to file them under "Not found (404)". These are the real
  # ones. Do not move them back to .htaccess.
  rules {
    ref         = "retired_career_pages"
    description = "3 retired career pages -> breaking-into-cloud-security.html"
    # "in { ... }" is set membership: true if the path equals any listed value.
    # Members are space-separated, NOT comma-separated - a comma is a syntax
    # error in this expression language.
    expression = "http.request.uri.path in {\"/is-cloud-security-a-good-career.html\" \"/get-into-cloud-security-no-experience.html\" \"/help-desk-to-cloud-security.html\"}"
    action     = "redirect"
    enabled    = true
    action_parameters {
      from_value {
        status_code = 301
        # These pages never took query parameters; drop anything appended.
        preserve_query_string = false
        target_url { value = "https://csoh.org/breaking-into-cloud-security.html" }
      }
    }
  }

  # ---------------------------------------------------------------------------
  # Legacy Concrete CMS (/conc8/) - the bulk of the Search Console 404s
  # ---------------------------------------------------------------------------
  # The pre-static site ran Concrete CMS under /conc8/, whose front controller
  # put the page path after index.php (e.g. /conc8/index.php/blog/calendar).
  # infra/README.md's cutover step 4 has always told you to verify a /conc8/
  # redirect with curl, but no rule was ever written - the check would have
  # failed if anyone had run it.
  #
  # Google still has the whole tree. The Search Console "Not found (404)" export
  # of 2026-08-09 held 224 URLs, and 220 of them were /conc8/*. The buckets, and
  # what each rule below covers:
  #
  #   100  /conc8/index.php/cloud-security-resources/<slug>   -> conc8_resources
  #     8  /conc8/index.php/resources/<slug>                  -> conc8_resources
  #     4  /conc8/index.php/blog/<slug>                        -> conc8_blog
  #     1  /conc8/index.php/kevin-mitnick                      -> conc8_mitnick
  #    55  /conc8, /conc8/, /conc8/index[.php] (+ query junk)  -> conc8_root
  #    52  /conc8/concrete/*                                   -> DELIBERATELY 404
  #
  # Two notes on what is NOT redirected:
  #
  #   - /conc8/concrete/* is Concrete's own installed source tree: vendor/,
  #     src/, themes/, and browsable directory listings. Google indexed 52 of
  #     them, including a stray error_log. None of it was ever content, none of
  #     it has a successor, and a 404 is the correct, honest answer. (That these
  #     were publicly crawlable at all was a real exposure on the old stack; it
  #     died with the migration to static hosting.)
  #   - /cdn-cgi/l/email-protection is a Cloudflare Email Obfuscation artifact,
  #     not our URL. Nothing to do.
  #
  # Every rule sets preserve_query_string = false on purpose. 88 of the 224 URLs
  # carry CMS pagination junk - ?ccm_paging_p_b2968=3&ccm_order_by_b2968=RAND(
  # 1633498375)&... - because the block re-seeded RAND() on every render, so the
  # old site minted a brand-new URL each time Googlebot looked at it. That is
  # what inflated one page into 55. Carrying those params through the redirect
  # would rebuild the same infinite crawl space on the new URLs.
  # ---------------------------------------------------------------------------

  # Exact 1:1 match - the old Mitnick page still exists at a new path.
  rules {
    ref         = "conc8_mitnick"
    description = "/conc8/index.php/kevin-mitnick -> /kevin-mitnick.html"
    expression  = "http.request.uri.path eq \"/conc8/index.php/kevin-mitnick\""
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/kevin-mitnick.html" }
      }
    }
  }

  # 108 per-resource CMS pages. Each was a standalone page for one tool or link;
  # that content now lives as cards on resources.html, so the category page is
  # the genuine successor rather than a stand-in. Not a soft-404 pattern: the
  # destination really does contain what the old URL described.
  rules {
    ref         = "conc8_resources"
    description = "/conc8/index.php/{cloud-security-,}resources/* -> /resources.html"
    expression  = "starts_with(http.request.uri.path, \"/conc8/index.php/cloud-security-resources\") or starts_with(http.request.uri.path, \"/conc8/index.php/resources\")"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/resources.html" }
      }
    }
  }

  # The old blog tree: /blog/calendar, /blog/presentations,
  # /blog/open-session-summaries, /blog/topic/207/podcasts. This is the redirect
  # infra/README.md's cutover step 4 has always claimed to verify.
  rules {
    ref         = "conc8_blog"
    description = "/conc8/index.php/blog/* -> /news.html"
    expression  = "starts_with(http.request.uri.path, \"/conc8/index.php/blog\")"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/news.html" }
      }
    }
  }

  # The old CMS root and its front-controller spellings -> the new home page.
  # Matched by exact path (not a /conc8 prefix) so that /conc8/concrete/* falls
  # through to a 404 as described above. Query strings are ignored by an
  # http.request.uri.path test, so this one rule absorbs all 55 RAND() variants.
  #
  # The bare /index.php and /index.php/ spellings were folded in here on
  # 2026-08-09 (previously the separate bare_index_php rule). Same destination,
  # same status code, same query-string handling - one rule where there were
  # two, which is what paid for one of the four directory redirects below.
  rules {
    ref         = "conc8_root"
    description = "/conc8 root + bare /index.php front-controller spellings -> home"
    expression  = "http.request.uri.path in {\"/conc8\" \"/conc8/\" \"/conc8/index\" \"/conc8/index.php\" \"/conc8/index.php/\" \"/index.php\" \"/index.php/\"}"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/" }
      }
    }
  }

  # ---------------------------------------------------------------------------
  # Section directories -> their index page
  # ---------------------------------------------------------------------------
  # The site is flat files, so /meetings/ has no index document and the four
  # content subdirectories are dead URLs - the kind people type, link, and
  # guess. Worse, they answered inconsistently: sampling /homelab/ twelve times
  # returned a mix of 403 and 404, because S3 replies 403 (AccessDenied) for a
  # missing key while nginx and Azure reply 404. Cloudflare load-balances
  # across all three, so the response depended on which origin caught the
  # request. That split is what put entries in Search Console's "Blocked due
  # to access forbidden (403)" bucket, and it is invisible to any check that
  # fetches a URL once.
  #
  # These four are separate rules rather than one wildcard_replace, because
  # only meetings/ follows the <dir>.html pattern. The targets come from
  # active_href_for() in tools/sync_chrome.py, which is the existing source of
  # truth for "which top-level page owns this subdirectory" - keep them in step.
  #
  # Each rule covers the bare and trailing-slash spellings both.
  rules {
    ref         = "dir_meetings"
    description = "/meetings[/] -> /meetings.html"
    expression  = "http.request.uri.path in {\"/meetings\" \"/meetings/\"}"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/meetings.html" }
      }
    }
  }

  rules {
    ref         = "dir_breaches"
    description = "/breaches[/] -> /breach-timeline.html"
    expression  = "http.request.uri.path in {\"/breaches\" \"/breaches/\"}"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/breach-timeline.html" }
      }
    }
  }

  rules {
    ref         = "dir_portfolio"
    description = "/portfolio[/] -> /cloud-security-portfolio-projects.html"
    expression  = "http.request.uri.path in {\"/portfolio\" \"/portfolio/\"}"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/cloud-security-portfolio-projects.html" }
      }
    }
  }

  rules {
    ref         = "dir_homelab"
    description = "/homelab[/] -> /cloud-security-home-lab.html"
    expression  = "http.request.uri.path in {\"/homelab\" \"/homelab/\"}"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/cloud-security-home-lab.html" }
      }
    }
  }
}

# =============================================================================
# Cache rules - uniform caching across all three origins
# -----------------------------------------------------------------------------
# The object-storage origins (S3, Azure) don't emit the same Cache-Control the
# nginx container did, so we set caching at the edge instead. edge_ttl controls
# Cloudflare's cache; browser_ttl sets the Cache-Control max-age sent to the
# client. Mirrors the nginx tiers: search.html 60s, HTML/XML 1h, assets 1y.
# =============================================================================
# A third ruleset, in the cache-settings phase. These rules decide how long each
# kind of file is cached - at Cloudflare's edge AND in the visitor's browser.
resource "cloudflare_ruleset" "cache" {
  zone_id     = var.zone_id
  name        = "csoh-cache"
  description = "Edge + browser cache tiers (mirrors nginx Cache-Control)"
  kind        = "zone"
  # This phase runs on the request and lets us override caching behavior before
  # Cloudflare decides whether to serve from cache or fetch from an origin.
  phase = "http_request_cache_settings"

  # Tier 1: the search page. It must stay fresh, so cache it only briefly.
  rules {
    ref         = "cache_search_html"
    description = "search.html - effectively uncached (60s)"
    # Match exactly the /search.html path, on a production hostname. See the
    # QA rule at the bottom of this ruleset for why every tier here carries
    # that host exclusion.
    expression = "http.request.uri.path eq \"/search.html\" and http.host ne \"qa.${var.zone_name}\""
    # This action sets the caching rules carried in action_parameters below.
    action  = "set_cache_settings"
    enabled = true
    action_parameters {
      # Allow this response to be cached at all.
      cache = true
      # "edge_ttl" = how long Cloudflare's edge servers keep the cached copy.
      edge_ttl {
        # "override_origin" = ignore whatever Cache-Control the origin sent and
        # use our "default" instead. Needed because S3/Azure don't send the
        # Cache-Control values the old nginx origin did.
        mode = "override_origin"
        # TTL ("time to live") in seconds: 60s = 1 minute.
        default = 60
      }
      # "browser_ttl" = the max-age Cloudflare puts in Cache-Control for the
      # visitor's browser. Same 60s short window here.
      browser_ttl {
        mode    = "override_origin"
        default = 60
      }
    }
  }

  # Tier 2: static assets (CSS/JS/images). These rarely change and are safe to
  # cache for a very long time.
  rules {
    ref         = "cache_assets_immutable"
    description = "CSS/JS/images - 1 year immutable"
    # Match by file extension. "in { ... }" tests whether the URL's extension is
    # one of the listed values (space-separated set).
    expression = "http.request.uri.path.extension in {\"css\" \"js\" \"png\" \"jpg\" \"jpeg\" \"gif\" \"webp\" \"svg\" \"ico\"} and http.host ne \"qa.${var.zone_name}\""
    action     = "set_cache_settings"
    enabled    = true
    action_parameters {
      cache = true
      edge_ttl {
        mode = "override_origin"
        # 31536000 seconds = 365 days (1 year).
        default = 31536000
      }
      browser_ttl {
        mode    = "override_origin"
        default = 31536000
      }
    }
  }

  # Tier 3: pages and text documents. These change more often than assets, so
  # cache for a moderate window.
  rules {
    ref         = "cache_html_xml_short"
    description = "HTML/XML/JSON/TXT + extensionless pages - 1 hour, revalidate"
    # Match by extension, PLUS the extensionless cases. That last part matters:
    # this rule used to be `extension in {"html" "xml"}` alone, and
    # http.request.uri.path.extension is empty for "/" and for any clean URL
    # like "/about". Those matched no cache rule at all, fell through to
    # Cloudflare's default - which does NOT cache HTML - and returned
    # cf-cache-status: DYNAMIC, i.e. every single request for the home page was
    # forwarded to an origin. "json" and "txt" are here for the same reason:
    # /search-index.json is the largest file on the site (3.5 MB) and was being
    # served uncached on every search-page load.
    #
    # ends_with() and eq are plain string functions, not regex - the zone is on
    # a Cloudflare plan without regex support in rule expressions, so `matches`
    # is not available here.
    #
    # The trailing "and path ne /search.html" is load-bearing. Cache rules apply
    # the LAST matching rule, not the first, so this rule was already silently
    # overriding the 60-second search.html rule above it: production served
    # search.html with max-age=3600, never 60. Excluding it here restores that
    # rule's intent and makes the outcome independent of rule ordering.
    #
    # Parentheses are required: `and` binds tighter than `or`, so without them
    # the exclusion would attach only to the last `or` branch.
    expression = "(http.request.uri.path.extension in {\"html\" \"xml\" \"json\" \"txt\"} or http.request.uri.path.extension eq \"\" or ends_with(http.request.uri.path, \"/\")) and http.request.uri.path ne \"/search.html\" and http.host ne \"qa.${var.zone_name}\""
    action     = "set_cache_settings"
    enabled    = true
    action_parameters {
      cache = true
      edge_ttl {
        mode = "override_origin"
        # 3600 seconds = 1 hour.
        default = 3600
      }
      browser_ttl {
        mode    = "override_origin"
        default = 3600
      }
    }
  }

  # QA: never cache anything on qa.csoh.org.
  #
  # Without this, tier 3 above would hold a QA page at the edge for an hour,
  # which makes the environment useless for its one job - you push a fix, reload,
  # and see the old page with no indication why. QA traffic is a handful of
  # requests from a handful of people, so there is nothing to gain by caching it.
  #
  # ON PLACEMENT, which is the trap this ruleset has already sprung once. Cache
  # rules apply the LAST matching rule, not the first: that is how the tier 3
  # rule silently overrode the 60-second search.html rule above it for as long
  # as both existed, and production served search.html with max-age=3600. So the
  # fix here is NOT to rely on this rule sitting at the bottom. Every tier above
  # carries `and http.host ne "qa.csoh.org"`, which makes their match sets
  # DISJOINT from this one - no request can satisfy both a tier rule and this
  # rule, so which one comes last stops mattering. Moving this block, or
  # inserting a fourth tier below it, cannot break QA caching. Prefer that shape
  # over a carefully ordered list; ordering is a comment that does not run.
  rules {
    ref         = "cache_qa_bypass"
    description = "qa.csoh.org - bypass cache entirely"
    expression  = "http.host eq \"qa.${var.zone_name}\""
    action      = "set_cache_settings"
    enabled     = true
    action_parameters {
      # false = do not cache this response at the edge at all, and do not serve
      # it from cache. Every QA request reaches the Cloud Run QA service.
      cache = false
    }
  }
}

# =============================================================================
# Origin rules - route qa.csoh.org to the QA Cloud Run service
# -----------------------------------------------------------------------------
# A fourth ruleset, in a phase this stack did not use before. It exists to solve
# one specific problem: Cloud Run decides WHICH service a request is for by
# reading the Host header, and it now runs two services in this project.
#
# The DNS record in qa.tf points qa.csoh.org at the QA service's *.run.app
# hostname, but a proxied record sends the ORIGINAL Host header to the origin.
# So Cloud Run would receive `Host: qa.csoh.org`, match that against no service
# it knows, and answer 404 for every request - a failure that looks like a
# broken deploy rather than a missing header rewrite, because the DNS resolves
# correctly, TLS completes, and Access logs the visitor in first.
#
# Production does not need this rule: its origins sit in a Load Balancer pool,
# and each pool origin in load_balancer.tf sets its own `host_header` override.
# QA is deliberately outside that pool (see qa.tf for the cost reason), so the
# override has to be made here instead.
# =============================================================================
resource "cloudflare_ruleset" "origin_qa" {
  zone_id     = var.zone_id
  name        = "csoh-origin-qa"
  description = "Rewrite Host + origin for qa.csoh.org so Cloud Run resolves the QA service"
  kind        = "zone"
  # This phase runs after Cloudflare has decided to go to an origin, and lets
  # us change WHICH origin and WHAT Host header it is asked with.
  phase = "http_request_origin"

  rules {
    ref         = "origin_qa_host_rewrite"
    description = "qa.csoh.org - send to the QA Cloud Run service"
    expression  = "http.host eq \"qa.${var.zone_name}\""
    # "route" is the action that overrides origin/Host for the matched request.
    action  = "route"
    enabled = true
    action_parameters {
      # The Host header Cloud Run actually sees. This is the line that makes
      # the difference between a working QA site and a uniform 404.
      host_header = var.gcp_qa_origin_host
      # Where to connect. Strictly speaking the DNS CNAME already resolves
      # here, so this is belt and braces - but stating it means the routing no
      # longer depends on the DNS record's target being right, and the two
      # cannot drift apart into a state where requests land on the production
      # service while carrying a QA Host header.
      origin {
        host = var.gcp_qa_origin_host
      }
    }
  }
}
