# A "variable" is a named input to this Terraform configuration: a value the
# code does NOT hardcode, so it can be supplied from outside (a .tfvars file,
# a -var flag, or an environment variable named TF_VAR_<name>). Inside the
# other .tf files in this folder these are read as var.<name> (for example
# var.account_id below). Keeping IDs in variables means the same code can be
# pointed at a different Cloudflare account/zone without editing it.
#
# Cloudflare has two levels of object. An ACCOUNT is your top-level Cloudflare
# login/organization; a ZONE is one domain inside that account (here csoh.org).
# Some objects belong to the account, others to a single zone. The Load
# Balancer "pool" and health "monitor" (see load_balancer.tf) are
# account-scoped, so they need this account ID.
#
# "type = string" declares that this value must be plain text. There is no
# "default", which makes this variable REQUIRED: Terraform will refuse to run
# until a value is provided. (Account/zone IDs are deployment-specific, so
# there is no sensible built-in default to ship in the repo.)
variable "account_id" {
  description = "Cloudflare account ID that owns the zone (Load Balancer pools + monitors are account-scoped)."
  type        = string
}

# The zone-level identifier for the csoh.org domain. Zone-scoped resources —
# the DNS records, the Load Balancer published at the apex, and the zone TLS
# settings (zone.tf) — are attached to this zone via var.zone_id. Also
# required (no default), for the same reason as account_id.
variable "zone_id" {
  description = "Cloudflare zone ID for csoh.org."
  type        = string
}

# The human-readable domain name itself. "Apex" (also called the root or naked
# domain) means csoh.org with no subdomain in front — as opposed to
# www.csoh.org. This value names the Load Balancer and is the CNAME target for
# the www record (load_balancer.tf).
#
# Unlike the IDs above, this one HAS a "default", so the variable is OPTIONAL:
# if no value is supplied, Terraform uses "csoh.org". The default is safe to
# commit because the domain is public and unlikely to change.
variable "zone_name" {
  description = "Apex domain."
  type        = string
  default     = "csoh.org"
}

# The next three variables are the real addresses of the three "origins" —
# the actual servers behind Cloudflare that hold copies of the site (AWS
# CloudFront, GCP Cloud Run, Azure static website). Cloudflare's Load Balancer
# (load_balancer.tf) needs to know each origin's hostname so it can forward
# requests to them and health-check them.
#
# "no scheme" means provide just the hostname (e.g. d111.cloudfront.net), NOT
# https://d111.cloudfront.net — Cloudflare adds the protocol itself.
#
# These are kept as required variables (no defaults) and fed in at deploy time
# rather than hardcoded, because each one is an OUTPUT of a different Terraform
# project. The commands just below show exactly how each hostname is read from
# the aws/gcp/azure stacks' outputs, so the value here always matches whatever
# those stacks actually created — no copying stale hostnames by hand:
#   aws_origin_host   = terraform -chdir=../aws   output -raw cloudfront_domain
#   gcp_origin_host   = host part of  terraform -chdir=../gcp   output -raw cloud_run_service_url
#   azure_origin_host = terraform -chdir=../azure output -raw static_website_host
# The AWS origin: the *.cloudfront.net hostname of the CloudFront CDN that
# fronts the private S3 bucket. Used as one origin in the LB pool, and as that
# origin's Host header override (load_balancer.tf).
variable "aws_origin_host" {
  description = "AWS CloudFront distribution hostname (no scheme)."
  type        = string
}

# The GCP origin: the *.run.app hostname of the Cloud Run service (the nginx
# container that scales to zero). Note this is just the host part of the full
# Cloud Run service URL — see the command comment above for how it's extracted.
variable "gcp_origin_host" {
  description = "GCP Cloud Run *.run.app hostname (no scheme)."
  type        = string
}

# The Azure origin: the static-website endpoint hostname of the Storage
# Account's "$web" container (typically *.web.core.windows.net). The third
# origin in the LB pool.
variable "azure_origin_host" {
  description = "Azure $web static-website hostname (no scheme)."
  type        = string
}
