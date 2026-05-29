variable "aws_account_id" {
  description = "AWS account this stack must deploy into. Enforced via the provider's allowed_account_ids so a terraform apply against any other account (wrong profile / stale creds) aborts before touching anything."
  type        = string
  default     = "038416307420"
}

variable "aws_region" {
  description = "Region for the S3 origin bucket. CloudFront itself is global; us-east-1 keeps it conventional and is where ACM certs would live if we ever add a custom origin cert."
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Globally-unique S3 bucket name for the site origin. Not a website endpoint — the bucket stays private and is reached only via CloudFront OAC."
  type        = string
  default     = "csoh-org-site-origin"
}

variable "github_owner" {
  description = "GitHub org/user that owns the repo (scopes the OIDC trust)."
  type        = string
  default     = "CloudSecurityOfficeHours"
}

variable "github_repo" {
  description = "GitHub repo name (scopes the OIDC trust)."
  type        = string
  default     = "csoh.org"
}

variable "github_branch" {
  description = "Branch authorized to publish via OIDC."
  type        = string
  default     = "main"
}
