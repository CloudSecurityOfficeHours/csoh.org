# Cloudflare edge for csoh.org — the control plane that ties the three cloud
# origins together. This is where TLS termination, the active/active Load
# Balancer + health checks, security headers, legacy redirects, caching, and
# the (free) managed WAF all live. Previously most of this was the GCP load
# balancer + Cloud Armor; it now runs at Cloudflare's edge, once, in front of
# all three origins.
#
# State shares the GCP GCS bucket under a separate prefix.
#
# Auth: export CLOUDFLARE_API_TOKEN (scoped to this zone: DNS edit, Load
# Balancing edit, Zone settings edit, Ruleset edit). No token in the repo.
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }

  backend "gcs" {
    bucket = "csoh-org-495800-tfstate"
    prefix = "csoh/cloudflare"
  }
}

provider "cloudflare" {}
