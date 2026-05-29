# Keyless deploy from GitHub Actions — the AWS counterpart to GCP's
# Workload Identity Federation. GitHub mints an OIDC token for the workflow
# run; AWS STS exchanges it for short-lived credentials. No static
# AWS_ACCESS_KEY_ID secret ever lives in the repo.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC certs chain to a CA AWS already trusts, so the thumbprint
  # is no longer security-load-bearing — but the API still requires the
  # field. These are GitHub's published intermediate thumbprints.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fce",
  ]
}

# Trust policy: only this repo's `production` GitHub Environment may assume the
# role. Because the deploy jobs declare `environment: production`, GitHub mints
# the OIDC token with sub `repo:OWNER/REPO:environment:production` (NOT the
# `ref:refs/heads/...` form), so the condition must match that. The branch
# restriction is enforced by the GitHub Environment itself (main-only).
data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_owner}/${var.github_repo}:environment:production"]
    }
  }
}

resource "aws_iam_role" "publisher" {
  name               = "csoh-site-publisher"
  description        = "Assumed by GitHub Actions via OIDC to sync the site to S3 and invalidate CloudFront."
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

# Least privilege: write objects to the one bucket, list it (for `aws s3
# sync` delete reconciliation), and invalidate this one distribution.
data "aws_iam_policy_document" "publisher" {
  statement {
    sid       = "SyncSiteObjects"
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.site.arn, "${aws_s3_bucket.site.arn}/*"]
  }

  statement {
    sid       = "InvalidateDistribution"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [aws_cloudfront_distribution.site.arn]
  }
}

resource "aws_iam_role_policy" "publisher" {
  name   = "csoh-site-publisher-policy"
  role   = aws_iam_role.publisher.id
  policy = data.aws_iam_policy_document.publisher.json
}
