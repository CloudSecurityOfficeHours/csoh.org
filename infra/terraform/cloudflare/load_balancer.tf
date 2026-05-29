# Health monitor — Cloudflare probes each origin over HTTPS and pulls
# unhealthy origins out of rotation automatically. Because the three origins
# answer on different hostnames (cloudfront.net, run.app, web.core.windows.net)
# each pool origin sets its own Host header override below, which the monitor
# honors when probing.
resource "cloudflare_load_balancer_monitor" "site" {
  account_id       = var.account_id
  type             = "https"
  method           = "GET"
  path             = "/"
  expected_codes   = "200"
  interval         = 60
  timeout          = 5
  retries          = 2
  description      = "csoh.org origin health (HTTPS GET /)"
  allow_insecure   = false
  follow_redirects = false
}

# One pool holding all three origins. origin_steering "random" spreads live
# traffic across every healthy origin — this is the active/active behavior:
# AWS, GCP, and Azure all serve simultaneously, and any that fails its health
# check is skipped until it recovers.
#
# Each origin overrides the Host header to its own hostname. Without this,
# Cloudflare would forward Host: csoh.org and CloudFront / Cloud Run / Azure
# Blob would reject the request (they don't recognize that hostname).
resource "cloudflare_load_balancer_pool" "origins" {
  account_id         = var.account_id
  name               = "csoh-origins"
  description        = "AWS S3+CloudFront, GCP Cloud Run, Azure Blob static website"
  monitor            = cloudflare_load_balancer_monitor.site.id
  minimum_origins    = 1
  notification_email = ""

  origin_steering {
    policy = "random"
  }

  origins {
    name    = "aws-cloudfront"
    address = var.aws_origin_host
    enabled = true
    weight  = 1
    header {
      header = "Host"
      values = [var.aws_origin_host]
    }
  }

  origins {
    name    = "gcp-cloud-run"
    address = var.gcp_origin_host
    enabled = true
    weight  = 1
    header {
      header = "Host"
      values = [var.gcp_origin_host]
    }
  }

  origins {
    name    = "azure-blob"
    address = var.azure_origin_host
    enabled = true
    weight  = 1
    header {
      header = "Host"
      values = [var.azure_origin_host]
    }
  }
}

# The Load Balancer itself, published at the apex. proxied=true keeps it
# behind Cloudflare's edge (cache + TLS + WAF). steering_policy "off" means
# "use the default pool" — and since all three origins live in that one pool,
# origin_steering above does the active/active distribution.
resource "cloudflare_load_balancer" "site" {
  zone_id          = var.zone_id
  name             = var.zone_name
  default_pool_ids = [cloudflare_load_balancer_pool.origins.id]
  fallback_pool_id = cloudflare_load_balancer_pool.origins.id
  proxied          = true
  steering_policy  = "off"
  description      = "csoh.org active/active multi-cloud edge LB"
}

# www → apex, proxied. The apex is the Load Balancer; www is a normal proxied
# CNAME that flattens onto it.
resource "cloudflare_record" "www" {
  zone_id = var.zone_id
  name    = "www"
  type    = "CNAME"
  content = var.zone_name
  proxied = true
  ttl     = 1 # 1 = automatic (required when proxied)
}
