variable "account_id" {
  description = "Cloudflare account ID that owns the zone (Load Balancer pools + monitors are account-scoped)."
  type        = string
}

variable "zone_id" {
  description = "Cloudflare zone ID for csoh.org."
  type        = string
}

variable "zone_name" {
  description = "Apex domain."
  type        = string
  default     = "csoh.org"
}

# The three origin hostnames, taken from the other Terraform dirs' outputs:
#   aws_origin_host   = terraform -chdir=../aws   output -raw cloudfront_domain
#   gcp_origin_host   = host part of  terraform -chdir=../gcp   output -raw cloud_run_service_url
#   azure_origin_host = terraform -chdir=../azure output -raw static_website_host
variable "aws_origin_host" {
  description = "AWS CloudFront distribution hostname (no scheme)."
  type        = string
}

variable "gcp_origin_host" {
  description = "GCP Cloud Run *.run.app hostname (no scheme)."
  type        = string
}

variable "azure_origin_host" {
  description = "Azure $web static-website hostname (no scheme)."
  type        = string
}
