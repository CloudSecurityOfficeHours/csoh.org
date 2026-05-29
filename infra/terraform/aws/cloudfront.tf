# This file provisions AWS CloudFront (Amazon's CDN — content delivery
# network) plus the small "access control" object that lets CloudFront read
# our private S3 bucket. In Terraform, a `resource "TYPE" "NAME" { ... }`
# block declares one real cloud object that Terraform will create and manage:
# TYPE is the kind of object (here, a CloudFront origin access control),
# NAME ("site") is the local handle other blocks use to refer to it.
#
# What is CloudFront's role here? Even though Cloudflare is the public-facing
# CDN for csoh.org, CloudFront is the secure HTTPS doorway in front of the
# private S3 bucket (see s3.tf). Cloudflare's load balancer treats this
# CloudFront distribution as the "AWS origin" and forwards visitor requests
# to it; CloudFront in turn fetches the files from S3.
#
# This first resource is an Origin Access Control (OAC): the mechanism that
# lets CloudFront — and ONLY this CloudFront distribution — read the
# otherwise-private S3 bucket. OAC is the modern replacement for the older
# Origin Access Identity. Some terms: "SigV4" is AWS's standard
# request-signing scheme — CloudFront cryptographically signs each request it
# sends to S3 so S3 can verify the caller. "AWS:SourceArn" matches this
# distribution's ARN (Amazon Resource Name — the unique ID/address AWS assigns
# every object); the bucket policy in s3.tf pins that ARN, so no other caller
# is accepted. The net effect: the bucket needs zero public access.
resource "aws_cloudfront_origin_access_control" "site" {
  # A human-readable name for this OAC object within the AWS account.
  name = "csoh-s3-oac"
  # Free-text note shown in the AWS console; purely for humans.
  description = "OAC for csoh.org S3 origin"
  # Tells AWS the origin being protected is an S3 bucket (vs. a generic HTTP
  # server, which would use a different value here).
  origin_access_control_origin_type = "s3"
  # "always" = sign every request to S3, so S3 can always verify the caller.
  signing_behavior = "always"
  # Use AWS Signature Version 4, the standard signing algorithm.
  signing_protocol = "sigv4"
}

# The CloudFront distribution itself: the CDN endpoint that serves the site
# over HTTPS. Creating this gives us a hostname like d111111abcdef8.cloudfront.net
# (exported in outputs.tf) which Cloudflare uses as the AWS origin address.
resource "aws_cloudfront_distribution" "site" {
  # Turn the distribution on. Set to false to disable serving without
  # destroying the distribution.
  enabled = true
  # When a visitor requests the bare site root ("/"), serve index.html
  # instead of returning an empty/forbidden response.
  default_root_object = "index.html"
  # Free-text label for the distribution in the AWS console.
  comment = "csoh.org static origin (behind Cloudflare)"
  # Price class controls which of AWS's worldwide edge locations are used.
  # PriceClass_100 = only the cheapest regions (North America + Europe). That
  # is fine here because Cloudflare — not CloudFront — is the true global edge
  # that visitors actually hit; CloudFront only needs to serve Cloudflare.
  price_class = "PriceClass_100" # NA + EU edges; Cloudflare is the real global edge

  # An "origin" is the backend CloudFront pulls content from. Here it is our
  # S3 bucket. The values below reference OTHER resources by writing
  # `TYPE.NAME.attribute` — Terraform reads that attribute from the named
  # resource and automatically figures out the right creation order (the
  # bucket and the OAC are built before this distribution). These cross-block
  # references are how Terraform stitches infrastructure together.
  origin {
    # The bucket's region-specific DNS name (e.g.
    # csoh-org-site-origin.s3.us-east-1.amazonaws.com), pulled from the
    # aws_s3_bucket.site resource defined in s3.tf.
    domain_name = aws_s3_bucket.site.bucket_regional_domain_name
    # A label we choose to identify this origin; the cache behavior below
    # points at the same string to say "use this origin".
    origin_id = "s3-csoh-site"
    # Attach the OAC declared above so CloudFront signs its requests to S3.
    # `.id` is an attribute AWS fills in after the OAC is created.
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  # The default cache behavior defines how CloudFront handles requests: which
  # origin to use, what protocols/methods are allowed, and how to cache. This
  # is the "default" because it applies to all paths (no per-path overrides
  # are configured for this simple static site).
  default_cache_behavior {
    # Route requests to the S3 origin defined above (matches its origin_id).
    target_origin_id = "s3-csoh-site"
    # If a visitor somehow arrives over plain HTTP, send a redirect to HTTPS
    # so traffic is always encrypted.
    viewer_protocol_policy = "redirect-to-https"
    # HTTP verbs CloudFront will accept. GET/HEAD fetch pages; OPTIONS covers
    # browser CORS preflight checks. A static site never needs POST/PUT/etc.
    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    # Of those, only GET and HEAD responses are stored in the cache.
    cached_methods = ["GET", "HEAD"]
    # Let CloudFront gzip/brotli-compress responses to speed up delivery.
    compress = true

    # A "cache policy" decides what counts as a cache key and how long to
    # cache. This GUID is AWS's managed, pre-built "CachingOptimized" policy
    # (you reference managed policies by their fixed ID rather than defining
    # your own). Cache-Control on responses is driven by Cloudflare Cache Rules
    # at the public edge; CloudFront is a second-tier cache that simply honors
    # origin/forwarded behavior.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # Each custom_error_response block tells CloudFront: when the origin returns
  # this error status, serve one of OUR styled HTML error pages instead of
  # CloudFront's bare default message. ("error_code" is what S3 returns;
  # "response_code" is what the visitor finally sees; "response_page_path" is
  # the file to serve; "error_caching_min_ttl" is how long, in seconds, to
  # cache that error before re-asking the origin.)
  # 404: missing object (ListBucket is granted, so S3 returns a true 404).
  # 403: genuinely forbidden (should be rare — we simply don't upload
  #      sensitive files; see the publish exclude list in CI).
  custom_error_response {
    # Origin said "not found".
    error_code = 404
    # Keep telling the visitor "404 Not Found"...
    response_code = 404
    # ...but render our branded page for it.
    response_page_path = "/404.html"
    # Cache this 404 for at least 60s to avoid hammering the origin.
    error_caching_min_ttl = 60
  }

  custom_error_response {
    # Origin said "forbidden".
    error_code = 403
    # Preserve the 403 status for the visitor...
    response_code = 403
    # ...and show our branded 403 page.
    response_page_path = "/403.html"
    # Cache this 403 for at least 60s.
    error_caching_min_ttl = 60
  }

  # CloudFront requires a restrictions block. geo_restriction can allow or
  # block traffic by country; "none" means no geographic filtering here
  # (any country may reach the distribution). This argument is mandatory even
  # when you don't want to restrict anything.
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # The viewer_certificate block controls the HTTPS/TLS certificate this
  # distribution presents (a TLS certificate is what proves a server's
  # identity and encrypts the connection). "SNI" is the part of the TLS
  # handshake where the client says which hostname it wants. Since Cloudflare
  # reaches CloudFront via its built-in *.cloudfront.net hostname, AWS's free
  # default certificate already matches the SNI name — so Cloudflare origin TLS
  # can run at Full (strict), and there is no need to request an ACM certificate
  # (AWS Certificate Manager) or custom domain on this distribution, because the
  # public csoh.org certificate lives on Cloudflare, not here.
  viewer_certificate {
    # Use the no-cost AWS-provided cert that covers *.cloudfront.net.
    cloudfront_default_certificate = true
    # Refuse outdated, insecure TLS versions; require modern TLS 1.2+.
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
