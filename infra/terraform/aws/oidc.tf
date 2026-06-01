# This whole file sets up "keyless" deploys: GitHub Actions proves who it is
# to AWS using a short-lived, cryptographically-signed token (OIDC) instead of
# a long-lived access key/secret stored in the repo. Background concepts:
#   - "resource" = a real cloud object Terraform CREATES and manages (here, IAM
#     objects in AWS). "data" (further down) = something Terraform only READS or
#     computes, never creates.
#   - OIDC (OpenID Connect) = a standard login protocol. GitHub acts as an
#     "identity provider": for each workflow run it issues a signed token (a JWT)
#     describing that run. AWS can be told to trust those tokens.
#   - IAM = AWS's permission system (Identity and Access Management): "roles"
#     bundle permissions; something trusted can temporarily "assume" a role.
# Keyless deploy from GitHub Actions - the AWS counterpart to GCP's
# Workload Identity Federation. GitHub mints an OIDC token for the workflow
# run; AWS STS exchanges it for short-lived credentials. No static
# AWS_ACCESS_KEY_ID secret ever lives in the repo.
# Registers GitHub's OIDC service as a trusted identity provider INSIDE this AWS
# account. This is the one-time "we trust tokens signed by GitHub" declaration;
# the roles below then decide WHICH GitHub tokens may actually do anything.
resource "aws_iam_openid_connect_provider" "github" {
  # The issuer URL: the exact web address GitHub signs its OIDC tokens with.
  # AWS fetches GitHub's public signing keys from here to verify each token.
  url = "https://token.actions.githubusercontent.com"
  # The expected "audience" (aud) the token must be addressed to. GitHub stamps
  # each token with this value so a token meant for AWS STS can't be replayed
  # against some other service. "sts.amazonaws.com" is AWS's token-exchange API.
  client_id_list = ["sts.amazonaws.com"]

  # A "thumbprint" is a fingerprint (SHA-1 hash) of the TLS certificate that
  # secures the issuer URL above - historically AWS used it to pin who it was
  # talking to. GitHub's OIDC certs now chain to a CA AWS already trusts, so
  # these values are no longer security-load-bearing - but the API field is
  # still mandatory, hence the two published GitHub intermediate thumbprints
  # below.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fce",
  ]
}

# An IAM "policy" is just a JSON document listing what's allowed/denied. This
# `aws_iam_policy_document` data source is a Terraform helper that BUILDS that
# JSON for us in readable HCL instead of hand-writing JSON; ".json" on it later
# yields the rendered text. Being a "data" source, it creates nothing in AWS -
# it only assembles a value other resources consume.
# This particular document is a "trust policy" (a.k.a. assume-role policy): it
# answers the question "WHO is allowed to assume this role?" - not "what can the
# role then do" (that second question is answered by the separate policy below).
# Trust policy: only this repo's `production` GitHub Environment may assume the
# role. Because the deploy jobs declare `environment: production`, GitHub mints
# the OIDC token with sub `repo:OWNER/REPO:environment:production` (NOT the
# `ref:refs/heads/...` form), so the condition must match that. The branch
# restriction is enforced by the GitHub Environment itself (main-only).
data "aws_iam_policy_document" "github_assume" {
  # A policy is made of one or more "statements". Each statement = a rule.
  statement {
    # The single action this rule permits: exchange a web-identity (OIDC) token
    # for temporary AWS credentials. This is the API call GitHub Actions makes.
    actions = ["sts:AssumeRoleWithWebIdentity"]
    # "Allow" (vs "Deny") - this statement grants the action above.
    effect = "Allow"

    # "principals" = WHO this rule is about. "Federated" means an external
    # identity provider rather than an AWS user. The identifier points at the
    # OIDC provider we registered above - `aws_iam_openid_connect_provider.github.arn`
    # is a REFERENCE to that resource's ARN (its unique AWS ID). Terraform reads
    # these cross-references to learn the right order to create things in, so it
    # builds the provider first, then this policy that depends on it.
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    # "conditions" narrow the rule further by inspecting claims (fields) inside
    # the incoming OIDC token. Without these, ANY GitHub repo's token accepted
    # by the provider could assume the role - so these two checks are the real
    # security gate. "StringEquals" means the claim must match exactly.
    # First check: the token's "aud" (audience) claim must equal the AWS STS
    # audience. Confirms the token was minted for AWS and not some other system.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Second check: the "sub" (subject) claim identifies exactly which workflow
    # context produced the token. The "${...}" syntax is Terraform interpolation
    # - it substitutes variable values into the string. So with the defaults in
    # variables.tf this resolves to
    # "repo:CloudSecurityOfficeHours/csoh.org:environment:production", meaning
    # ONLY a job in this repo running in the "production" GitHub Environment is
    # trusted. Any other repo, fork, or environment is rejected.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_owner}/${var.github_repo}:environment:production"]
    }
  }
}

# The actual IAM role GitHub Actions becomes when it deploys. A role is an
# identity with no password - it's "assumed" temporarily and hands back
# short-lived credentials. Permissions are attached separately (just below).
resource "aws_iam_role" "publisher" {
  # Fixed, human-readable name; CI references the role by its ARN (see the
  # publisher_role_arn output) when it logs in.
  name        = "csoh-site-publisher"
  description = "Assumed by GitHub Actions via OIDC to sync the site to S3 and invalidate CloudFront."
  # Attach the trust policy built above as JSON: this is what makes ONLY the
  # approved GitHub workflow able to assume this role. ".json" renders the
  # policy-document data source into the JSON string AWS expects.
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

# This is the role's PERMISSIONS policy (what it may DO once assumed), as
# opposed to the trust policy above (who may assume it). "Least privilege" is
# the security principle of granting only the exact actions and exact targets a
# job needs and nothing more - here: write objects to the one bucket, list it
# (for `aws s3 sync` delete reconciliation), and invalidate this one
# distribution. So even if this token leaked, it could only touch this one
# site's bucket and CDN, not the rest of the account.
data "aws_iam_policy_document" "publisher" {
  # Statement 1: everything needed to publish the files to S3.
  statement {
    # "sid" is just a label for this statement, handy when reading the rendered
    # JSON; it has no effect on what's allowed.
    sid = "SyncSiteObjects"
    # Upload new files (PutObject), remove deleted ones (DeleteObject), and list
    # bucket contents (ListBucket) - exactly what `aws s3 sync` needs to make
    # the bucket match the built site, including pruning stale files.
    actions = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    # WHICH objects these actions apply to. S3 distinguishes the bucket itself
    # from the objects inside it: ListBucket targets the bucket ARN, while
    # Put/Delete target the objects, written as "<bucket-arn>/*" (the trailing
    # "/*" means "every object/key in this bucket"). `aws_s3_bucket.site.arn`
    # references the bucket defined in s3.tf, so the role is locked to that one
    # bucket and nothing else in the account.
    resources = [aws_s3_bucket.site.arn, "${aws_s3_bucket.site.arn}/*"]
  }

  # Statement 2: let CI flush the CDN cache after a deploy.
  statement {
    sid = "InvalidateDistribution"
    # "Invalidation" tells CloudFront to drop its cached copies so visitors get
    # the freshly uploaded files instead of stale ones. This is the only
    # CloudFront action granted.
    actions = ["cloudfront:CreateInvalidation"]
    # Scoped to just this site's distribution (defined in cloudfront.tf), again
    # by ARN reference - the role can't touch any other distribution.
    resources = [aws_cloudfront_distribution.site.arn]
  }
}

# Glue: attaches the permissions document above onto the role as an "inline"
# policy (one that lives directly on the role rather than being a standalone,
# reusable managed policy). After this, assuming the role grants exactly those
# S3 + CloudFront actions.
resource "aws_iam_role_policy" "publisher" {
  name = "csoh-site-publisher-policy"
  # Which role to attach to - `.id` here is the role's name. Referencing the
  # role resource also tells Terraform to create the role before this attachment.
  role = aws_iam_role.publisher.id
  # The permissions, rendered to JSON from the data source above.
  policy = data.aws_iam_policy_document.publisher.json
}
