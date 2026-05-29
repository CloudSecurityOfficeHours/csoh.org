# Private origin bucket. The site is NOT served from the S3 website
# endpoint (that's HTTP-only and would force Cloudflare→origin over plain
# HTTP). Instead the bucket stays fully private and CloudFront reaches it
# with Origin Access Control (see cloudfront.tf), so the only public
# surface is the CloudFront HTTPS distribution.
resource "aws_s3_bucket" "site" {
  bucket = var.bucket_name
}

# Versioning gives us a cheap rollback/forensics trail: a bad publish can
# be restored object-by-object, and accidental deletes are recoverable.
resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Belt-and-braces: even though the bucket policy below only grants
# CloudFront, block every public-access vector at the account-object level
# so a future careless ACL or policy edit can't silently expose the bucket.
resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    object_ownership = "BucketOwnerEnforced" # ACLs disabled; policy-only access
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Bucket policy: allow ONLY this CloudFront distribution to read objects,
# scoped by the distribution ARN via the standard OAC source-arn condition.
# No principals, no public read.
data "aws_iam_policy_document" "site_bucket" {
  statement {
    sid       = "AllowCloudFrontOACRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }

  # Grant ListBucket as well so a request for a missing key returns a real
  # 404 from S3. Without it, a private bucket answers AccessDenied (403)
  # for absent objects, which would force every "page not found" through
  # the 403 error mapping and mask genuine 403s. Scoped to CloudFront only.
  statement {
    sid       = "AllowCloudFrontOACList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.site.arn]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site_bucket.json
}
