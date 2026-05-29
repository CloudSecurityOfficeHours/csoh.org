# =============================================================================
# Response security headers — the edge equivalent of nginx-security-headers.conf
# -----------------------------------------------------------------------------
# Set once at Cloudflare, applied to every response regardless of which origin
# served it. This is the single source of truth for the site's security
# headers; keep the values in sync with nginx-security-headers.conf.
# =============================================================================
resource "cloudflare_ruleset" "security_headers" {
  zone_id     = var.zone_id
  name        = "csoh-security-headers"
  description = "Baseline security headers on every response (mirrors nginx-security-headers.conf)"
  kind        = "zone"
  phase       = "http_response_headers_transform"

  rules {
    ref         = "set_security_headers"
    description = "Set HSTS, CSP, and the rest on all responses"
    expression  = "true"
    action      = "rewrite"
    enabled     = true

    action_parameters {
      headers {
        name      = "Strict-Transport-Security"
        operation = "set"
        value     = "max-age=31536000; includeSubDomains; preload"
      }
      headers {
        name      = "X-Content-Type-Options"
        operation = "set"
        value     = "nosniff"
      }
      headers {
        name      = "X-Frame-Options"
        operation = "set"
        value     = "DENY"
      }
      headers {
        name      = "Referrer-Policy"
        operation = "set"
        value     = "strict-origin-when-cross-origin"
      }
      headers {
        name      = "Permissions-Policy"
        operation = "set"
        value     = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()"
      }
      headers {
        name      = "Content-Security-Policy"
        operation = "set"
        value     = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://csoh.org https://img.youtube.com https://i.ytimg.com data:; font-src 'self'; connect-src 'self'; frame-src https://www.youtube.com https://web.archive.org; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
      }
      headers {
        name      = "Cross-Origin-Opener-Policy"
        operation = "set"
        value     = "same-origin"
      }
      headers {
        name      = "Cross-Origin-Resource-Policy"
        operation = "set"
        value     = "same-origin"
      }
    }
  }
}

# =============================================================================
# Legacy redirects — the edge equivalent of the .htaccess RewriteRules
# -----------------------------------------------------------------------------
# Mirrors the /csoh/ prefix strip and the /conc8 (Concrete5) 301 map. Rules
# evaluate top-to-bottom; redirect is terminating, so specific mappings are
# ordered before the catch-alls. Verify with curl after apply (see the cutover
# runbook in infra/README.md).
# =============================================================================
resource "cloudflare_ruleset" "redirects" {
  zone_id     = var.zone_id
  name        = "csoh-legacy-redirects"
  description = "301 redirects for /csoh/ and legacy /conc8 Concrete5 URLs (mirrors .htaccess)"
  kind        = "zone"
  phase       = "http_request_dynamic_redirect"

  # --- /csoh/* prefix strip → / (dynamic target) ---
  rules {
    ref         = "csoh_prefix_strip"
    description = "/csoh/* -> /*"
    expression  = "starts_with(http.request.uri.path, \"/csoh/\")"
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = true
        target_url {
          expression = "concat(\"https://csoh.org\", regex_replace(http.request.uri.path, \"^/csoh/\", \"/\"))"
        }
      }
    }
  }

  # --- conc8 specific page mappings (most specific first) ---
  rules {
    ref         = "conc8_kevin_mitnick"
    description = "kevin-mitnick"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/kevin-mitnick/?$\""
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

  rules {
    ref         = "conc8_presentations"
    description = "blog/presentations"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/blog/presentations/?$\""
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/presentations.html" }
      }
    }
  }

  rules {
    ref         = "conc8_sessions"
    description = "blog/calendar + blog/open-session-summaries -> sessions"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/blog/(calendar|open-session-summaries)/?$\""
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/sessions.html" }
      }
    }
  }

  rules {
    ref         = "conc8_blog"
    description = "blog -> news"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/blog/?$\""
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

  rules {
    ref         = "conc8_certs"
    description = "resources/cwertification-resources -> certifications"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/resources/cwertification-resources/?$\""
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/cloud-security-certifications.html" }
      }
    }
  }

  rules {
    ref         = "conc8_puppies"
    description = "resources/cloud-security-training-puppies -> learning-path"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/resources/cloud-security-training-puppies/?$\""
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/learning-path.html" }
      }
    }
  }

  rules {
    ref         = "conc8_resources"
    description = "resources/* -> resources"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/resources(/.*)?$\""
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

  rules {
    ref         = "conc8_dated_sessions"
    description = "cloud-security-resources/NNNNNN-* -> sessions"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/cloud-security-resources/[0-9]{6}-.*$\""
    action      = "redirect"
    enabled     = true
    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = false
        target_url { value = "https://csoh.org/sessions.html" }
      }
    }
  }

  rules {
    ref         = "conc8_csr"
    description = "cloud-security-resources/* -> resources"
    expression  = "http.request.uri.path matches \"^/conc8/index\\.php/cloud-security-resources(/.*)?$\""
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

  # --- catch-alls (least specific, last) ---
  rules {
    ref         = "conc8_catch_all"
    description = "any other /conc8* -> home"
    expression  = "starts_with(http.request.uri.path, \"/conc8\")"
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

  rules {
    ref         = "bare_index_php"
    description = "/index.php -> home"
    expression  = "http.request.uri.path matches \"^/index\\.php/?$\""
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
}

# =============================================================================
# Cache rules — uniform caching across all three origins
# -----------------------------------------------------------------------------
# The object-storage origins (S3, Azure) don't emit the same Cache-Control the
# nginx container did, so we set caching at the edge instead. edge_ttl controls
# Cloudflare's cache; browser_ttl sets the Cache-Control max-age sent to the
# client. Mirrors the nginx tiers: search.html 60s, HTML/XML 1h, assets 1y.
# =============================================================================
resource "cloudflare_ruleset" "cache" {
  zone_id     = var.zone_id
  name        = "csoh-cache"
  description = "Edge + browser cache tiers (mirrors nginx Cache-Control)"
  kind        = "zone"
  phase       = "http_request_cache_settings"

  rules {
    ref         = "cache_search_html"
    description = "search.html — effectively uncached (60s)"
    expression  = "http.request.uri.path eq \"/search.html\""
    action      = "set_cache_settings"
    enabled     = true
    action_parameters {
      cache = true
      edge_ttl {
        mode    = "override_origin"
        default = 60
      }
      browser_ttl {
        mode    = "override_origin"
        default = 60
      }
    }
  }

  rules {
    ref         = "cache_assets_immutable"
    description = "CSS/JS/images — 1 year immutable"
    expression  = "http.request.uri.path matches \"\\.(css|js|png|jpe?g|gif|webp|svg|ico)$\""
    action      = "set_cache_settings"
    enabled     = true
    action_parameters {
      cache = true
      edge_ttl {
        mode    = "override_origin"
        default = 31536000
      }
      browser_ttl {
        mode    = "override_origin"
        default = 31536000
      }
    }
  }

  rules {
    ref         = "cache_html_xml_short"
    description = "HTML + XML — 1 hour, revalidate"
    expression  = "http.request.uri.path matches \"\\.(html|xml)$\""
    action      = "set_cache_settings"
    enabled     = true
    action_parameters {
      cache = true
      edge_ttl {
        mode    = "override_origin"
        default = 3600
      }
      browser_ttl {
        mode    = "override_origin"
        default = 3600
      }
    }
  }
}
