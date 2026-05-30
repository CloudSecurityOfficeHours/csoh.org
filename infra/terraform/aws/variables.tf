# This file declares this stack's INPUT VARIABLES. A Terraform "variable" is a
# named setting you can pass in from outside (on the command line, in a
# .tfvars file, or via an environment variable) so the same code can be reused
# with different values. Each block has three parts we use here:
#   - description: a human note explaining what the variable is for.
#   - type: the kind of value allowed; "string" means plain text. Terraform
#     rejects a wrong-typed value before doing anything.
#   - default: the value used when no override is supplied. Because every
#     variable below has a default, this stack runs with zero manual input —
#     the defaults ARE the real configuration for csoh.org.
# Other files refer to these as `var.<name>` (e.g. var.aws_region). That's how
# one value (like the region or bucket name) is written once here and reused
# everywhere, instead of being hardcoded in multiple places.
#
# Which AWS account this stack is allowed to deploy into. In versions.tf the
# provider sets `allowed_account_ids = [var.aws_account_id]`, a safety
# tripwire: if the credentials Terraform happens to be using point at any OTHER
# account (e.g. the wrong AWS profile, or stale leftover creds), the apply
# aborts immediately instead of creating this site's resources in the wrong
# place. The 12-digit string is the AWS account number.
variable "aws_account_id" {
  description = "AWS account this stack must deploy into. Enforced via the provider's allowed_account_ids so a terraform apply against any other account (wrong profile / stale creds) aborts before touching anything."
  type        = string
  default     = "038416307420"
}

# Which AWS geographic region to operate in. A "region" is a physical cluster
# of AWS data centers (e.g. us-east-1 = Northern Virginia); most AWS resources
# live in exactly one. versions.tf passes this to the provider as
# `region = var.aws_region`, which is then where the S3 origin bucket is
# created. CloudFront (the CDN) is a global service and isn't tied to a region,
# but us-east-1 is the conventional default and is the one region where AWS
# Certificate Manager (ACM) certs for CloudFront must live, so picking it keeps
# the door open if a custom origin certificate is ever added later.
variable "aws_region" {
  description = "Region for the S3 origin bucket. CloudFront itself is global; us-east-1 keeps it conventional and is where ACM certs would live if we ever add a custom origin cert."
  type        = string
  default     = "us-east-1"
}

# The name of the S3 bucket that stores the website's files (an S3 "bucket" is
# AWS's object-storage container). s3.tf uses this as `bucket = var.bucket_name`
# to create the bucket. Two things a novice should know: (1) S3 bucket names
# must be globally unique across ALL of AWS, not just this account — hence the
# specific, project-prefixed name; (2) this bucket is kept fully PRIVATE. The
# site is NOT served from S3's public "website endpoint"; instead CloudFront
# reaches the private bucket via Origin Access Control (OAC), so the only public
# surface is the HTTPS CloudFront distribution (details in s3.tf / cloudfront.tf).
variable "bucket_name" {
  description = "Globally-unique S3 bucket name for the site origin. Not a website endpoint — the bucket stays private and is reached only via CloudFront OAC."
  type        = string
  default     = "csoh-org-site-origin"
}

# The next three variables identify the exact GitHub source allowed to deploy
# this site, and together they "scope the OIDC trust." Background: deploys are
# keyless — instead of storing an AWS secret key, the GitHub Actions job proves
# its identity with a short-lived signed token (OIDC). oidc.tf builds an IAM
# trust rule that only accepts a token whose "subject" matches
# "repo:<github_owner>/<github_repo>:environment:production". These variables
# fill in that subject, so a token from any other org, repo, or environment is
# rejected. (The branch limit itself is enforced by GitHub's "production"
# Environment being main-only; see oidc.tf for the full explanation.)
#
# The GitHub organization (or user) that owns the repository. First half of the
# allowed OIDC subject; the default is this project's org.
variable "github_owner" {
  description = "GitHub org/user that owns the repo (scopes the OIDC trust)."
  type        = string
  default     = "CloudSecurityOfficeHours"
}

# The repository name within that org. Second half of the allowed OIDC
# subject; combined with github_owner it pins the trust to exactly this repo.
variable "github_repo" {
  description = "GitHub repo name (scopes the OIDC trust)."
  type        = string
  default     = "csoh.org"
}

# The branch authorized to publish. Note: with the current
# "environment:production" trust subject in oidc.tf, this variable is not
# actually interpolated into the trust condition — the branch restriction is
# enforced by GitHub's protected "production" Environment (configured to allow
# only main). It is kept here as the documented intent and in case the trust
# subject is ever switched back to the branch-based "ref:refs/heads/<branch>"
# form.
variable "github_branch" {
  description = "Branch authorized to publish via OIDC."
  type        = string
  default     = "main"
}
