# An `output` is a value Terraform prints after `terraform apply` and stores in
# its state file so other tools can read it. Think of outputs as the "return
# values" of this Terraform module: they expose a few useful facts about the
# real cloud objects we just created (names, IDs, addresses) so that humans and
# automation don't have to go hunting through the AWS console for them. Each
# `output "NAME" { ... }` block has a `description` (a human note) and a `value`
# (what to publish). The values here pull attributes off resources defined in
# the sibling files (s3.tf, cloudfront.tf, oidc.tf) by writing
# `TYPE.NAME.attribute`; the GitHub Actions deploy workflow reads these outputs
# so it knows which bucket to upload to, which CDN to refresh, and which role to
# log in as - all without any value being hardcoded twice.
#
# The public hostname AWS assigned to the CloudFront distribution, e.g.
# "d111111abcdef8.cloudfront.net". Cloudflare's load balancer is configured to
# treat this hostname as the "AWS origin" - the backend it forwards visitor
# traffic to when it picks the AWS cloud. Publishing it as an output means the
# address can be wired into the Cloudflare config without copy-pasting by hand.
output "cloudfront_domain" {
  description = "CloudFront distribution hostname - this is the Cloudflare LB origin address for AWS."
  value       = aws_cloudfront_distribution.site.domain_name
}

# CloudFront's internal ID for the distribution (e.g. "E1A2B3C4D5E6F7"), which
# is different from the hostname above. After every deploy, the CI pipeline runs
# `aws cloudfront create-invalidation` to tell CloudFront to throw away its
# cached copies of the old files; that command needs the distribution ID to know
# WHICH distribution to clear. Exporting it here lets the workflow grab the ID
# straight from Terraform instead of being told it separately.
output "cloudfront_distribution_id" {
  description = "Distribution ID for `aws cloudfront create-invalidation` in CI."
  value       = aws_cloudfront_distribution.site.id
}

# The name of the private S3 bucket that holds the site's files (defined in
# s3.tf). During a deploy, CI runs `aws s3 sync ./build s3://<this-name>` to copy
# the freshly built site into the bucket; it needs the exact bucket name to
# target. Exposing it as an output keeps the workflow and Terraform in agreement
# about which bucket is the AWS origin.
output "bucket_name" {
  description = "S3 origin bucket for `aws s3 sync` in CI."
  value       = aws_s3_bucket.site.bucket
}

# The ARN (Amazon Resource Name - AWS's globally-unique ID for an object) of the
# IAM role that GitHub Actions temporarily "assumes" to deploy, defined in
# oidc.tf. Remember deploys are keyless: instead of a stored access key, the
# workflow presents a short-lived OIDC token and asks AWS to let it become this
# role. To start that exchange, the GitHub Actions login step must be told the
# role's ARN, so we publish it here. The ARN is not a secret (it grants nothing
# on its own - only the approved workflow can actually assume the role), so this
# output is plain text and is intentionally not marked `sensitive`.
output "publisher_role_arn" {
  description = "IAM role ARN the GitHub Actions publish job assumes via OIDC."
  value       = aws_iam_role.publisher.arn
}
