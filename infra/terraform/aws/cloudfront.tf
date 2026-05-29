# Origin Access Control — the modern replacement for Origin Access
# Identity. CloudFront signs origin requests with SigV4 so S3 can verify
# they came from this distribution (matched by AWS:SourceArn in the bucket
# policy). The bucket needs no public access at all.
resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "csoh-s3-oac"
  description                       = "OAC for csoh.org S3 origin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "csoh.org static origin (behind Cloudflare)"
  price_class         = "PriceClass_100" # NA + EU edges; Cloudflare is the real global edge

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-csoh-site"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-csoh-site"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # AWS managed "CachingOptimized" policy. Cache-Control on responses is
    # driven by Cloudflare Cache Rules at the public edge; CloudFront is a
    # second-tier cache that simply honors origin/forwarded behavior.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # Map S3/CloudFront errors to the site's own static error pages.
  # 404: missing object (ListBucket is granted, so S3 returns a true 404).
  # 403: genuinely forbidden (should be rare — we simply don't upload
  #      sensitive files; see the publish exclude list in CI).
  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 60
  }

  custom_error_response {
    error_code            = 403
    response_code         = 403
    response_page_path    = "/403.html"
    error_caching_min_ttl = 60
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Cloudflare connects to this distribution by its *.cloudfront.net
  # hostname, so the default CloudFront certificate is valid for the SNI
  # name and Cloudflare origin TLS can run at Full (strict). No ACM cert
  # or custom domain is needed on the distribution itself.
  viewer_certificate {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1.2_2021"
  }
}
