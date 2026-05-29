output "cloudfront_domain" {
  description = "CloudFront distribution hostname — this is the Cloudflare LB origin address for AWS."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "cloudfront_distribution_id" {
  description = "Distribution ID for `aws cloudfront create-invalidation` in CI."
  value       = aws_cloudfront_distribution.site.id
}

output "bucket_name" {
  description = "S3 origin bucket for `aws s3 sync` in CI."
  value       = aws_s3_bucket.site.bucket
}

output "publisher_role_arn" {
  description = "IAM role ARN the GitHub Actions publish job assumes via OIDC."
  value       = aws_iam_role.publisher.arn
}
