# Cloudflare edge for csoh.org - the control plane that ties the three cloud
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
# The "terraform" block holds settings for Terraform itself (not for any cloud).
# It is where you pin tool/provider versions and say where state is stored. This
# is global configuration, evaluated before any resource is created.
terraform {
  # Refuse to run unless the Terraform CLI is at least version 1.6.0. Pinning a
  # minimum version means everyone (and CI) uses a Terraform new enough to
  # understand the syntax and features below, instead of failing in confusing
  # ways on an old binary.
  required_version = ">= 1.6.0"

  # A "provider" is the plugin that teaches Terraform how to talk to one specific
  # platform's API (here, Cloudflare). Terraform core has no built-in knowledge
  # of any cloud - every cloud object is managed through its provider plugin.
  # "required_providers" declares which provider plugins this folder needs and
  # which versions are acceptable, so Terraform can download the right ones.
  required_providers {
    # Declare the Cloudflare provider. The local name "cloudflare" is how we
    # refer to it elsewhere (e.g. the resource type "cloudflare_zone_settings_override").
    cloudflare = {
      # "source" is the global address of the plugin in Terraform's public
      # registry: the "cloudflare" namespace publishing the "cloudflare" provider.
      source = "cloudflare/cloudflare"
      # "~> 4.0" is a pessimistic version constraint: allow any 4.x release
      # (4.0, 4.1, 4.9, ...) but NOT 5.0. This lets us pick up bug fixes while
      # blocking the breaking 5.x rewrite. (MEMORY note: a v5 upgrade is pending,
      # and the rest of this folder is written against the v4 schema.)
      version = "~> 4.0"
    }
  }

  # The "backend" decides WHERE Terraform stores its state file - the JSON record
  # mapping the resources defined here to the real objects that exist in
  # Cloudflare. By default state is a local file, but that doesn't work for a
  # team or CI; "gcs" keeps it in a Google Cloud Storage bucket so every run
  # reads/writes the same shared, lockable state. (This Cloudflare folder reuses
  # the same bucket the GCP setup already created.)
  backend "gcs" {
    # The exact GCS bucket that holds the state object.
    bucket = "csoh-org-495800-tfstate"
    # A folder-like key prefix inside that bucket. Each Terraform dir uses its
    # own prefix (here "csoh/cloudflare") so the AWS/GCP/Azure/Cloudflare states
    # live side by side in one bucket without overwriting each other.
    prefix = "csoh/cloudflare"
  }
}

# Configure the Cloudflare provider declared above. The block is intentionally
# empty: we deliberately do NOT put the API token here (secrets must never live
# in the repo). Instead the provider reads the CLOUDFLARE_API_TOKEN environment
# variable automatically at runtime - see the auth note in the header above.
provider "cloudflare" {}
