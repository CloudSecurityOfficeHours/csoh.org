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

# The zone-level identifier for the csoh.org domain. Zone-scoped resources -
# the DNS records, the Load Balancer published at the apex, and the zone TLS
# settings (zone.tf) - are attached to this zone via var.zone_id. Also
# required (no default), for the same reason as account_id.
variable "zone_id" {
  description = "Cloudflare zone ID for csoh.org."
  type        = string
}

# The human-readable domain name itself. "Apex" (also called the root or naked
# domain) means csoh.org with no subdomain in front - as opposed to
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

# The next three variables are the real addresses of the three "origins" -
# the actual servers behind Cloudflare that hold copies of the site (AWS
# CloudFront, GCP Cloud Run, Azure static website). Cloudflare's Load Balancer
# (load_balancer.tf) needs to know each origin's hostname so it can forward
# requests to them and health-check them.
#
# "no scheme" means provide just the hostname (e.g. d111.cloudfront.net), NOT
# https://d111.cloudfront.net - Cloudflare adds the protocol itself.
#
# These are kept as required variables (no defaults) and fed in at deploy time
# rather than hardcoded, because each one is an OUTPUT of a different Terraform
# project. The commands just below show exactly how each hostname is read from
# the aws/gcp/azure stacks' outputs, so the value here always matches whatever
# those stacks actually created - no copying stale hostnames by hand:
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
# Cloud Run service URL - see the command comment above for how it's extracted.
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

# The QA origin: the *.run.app hostname of the SECOND Cloud Run service
# (csoh-site-qa), which serves qa.csoh.org. Read it the same way as the three
# above, from the gcp stack's outputs:
#   gcp_qa_origin_host = host part of \
#     terraform -chdir=../gcp output -raw cloud_run_qa_service_url
#
# Note what this variable is NOT used for. It is deliberately absent from the
# Load Balancer pool in load_balancer.tf: pool members are health-checked from
# every Cloudflare data center, roughly 1.09M probes per origin per day, which
# is what produced a $119.77 Azure bandwidth bill. QA is reached by a plain
# proxied DNS record (qa.tf) plus a Host-header rewrite (rules.tf) instead, so
# it is never probed and can scale to zero.
variable "gcp_qa_origin_host" {
  description = "GCP Cloud Run *.run.app hostname for the QA service (no scheme)."
  type        = string
}

# Who may log in to qa.csoh.org through Cloudflare Access. Every address listed
# here can request a one-time code by email and, on entering it, reach the QA
# site; nobody else gets past the login page.
#
# Deliberately has NO default, which makes it required. Two reasons. First, a
# default would put personal email addresses into a file this repo PUBLISHES -
# everything under infra/ is served on the site as teaching material for
# terraform.html, since tools/site-publish.filter does not exclude it. Second,
# an empty value fails in the most annoying direction: it would build a login
# page that the site's owner cannot get through.
#
# Enforcing this list also requires an email login method to exist. One-Time PIN
# is enabled on the account (as a `onetimepin` identity provider); if it is ever
# removed, the login page falls back to offering only "Cloudflare" account
# sign-in and every address here stops matching.
#
# Terraform reads it from TF_VAR_qa_allowed_emails like the others, but because
# it is a LIST rather than a string the environment variable has to carry JSON,
# and it is worth single-quoting so the brackets are never exposed to globbing:
#   TF_VAR_qa_allowed_emails='["you@example.com","reviewer@example.com"]'
variable "qa_allowed_emails" {
  description = "Email addresses allowed through Cloudflare Access to qa.csoh.org."
  type        = list(string)

  # A policy with an empty include matches nobody, which presents as a login
  # page that rejects every address rather than as a configuration error. Fail
  # at plan time instead.
  validation {
    condition     = length(var.qa_allowed_emails) > 0
    error_message = "qa_allowed_emails must list at least one address, or nobody can reach qa.csoh.org. Set TF_VAR_qa_allowed_emails='[\"you@example.com\"]'."
  }
}
