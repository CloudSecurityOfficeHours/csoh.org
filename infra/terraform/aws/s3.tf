# Private origin bucket. The site is NOT served from the S3 website
# endpoint (that's HTTP-only and would force Cloudflare→origin over plain
# HTTP). Instead the bucket stays fully private and CloudFront reaches it
# with Origin Access Control (see cloudfront.tf), so the only public
# surface is the CloudFront HTTPS distribution.
#
# A `resource "TYPE" "NAME" { ... }` block declares one real cloud object
# Terraform will create and manage. TYPE is the kind of object
# (aws_s3_bucket = an S3 storage bucket); NAME ("site") is the local handle
# other blocks use to refer to it, e.g. aws_s3_bucket.site.id. S3 is AWS's
# object storage - think of a bucket as a private folder that holds the
# website's files.
resource "aws_s3_bucket" "site" {
  # The bucket's globally-unique name. `var.bucket_name` pulls the value from
  # the `bucket_name` variable in variables.tf (default "csoh-org-site-origin").
  # `var.` is how Terraform reads an input variable - keeping the name in one
  # place rather than hard-coding it here.
  bucket = var.bucket_name
}

# Versioning is SUSPENDED, on purpose. It was "Enabled" until 2026-09-13, as a
# rollback trail, and it turned out to be an unbounded one. Versioning makes S3
# keep every past copy of a file, and the deploy re-uploads the whole site on
# every run (a fresh CI checkout gives every file a new timestamp, so
# `aws s3 sync` treats all of them as changed). So each deploy stored one more
# full copy of the site: by September 2026 that was ~2.77 million old versions,
# ~234 GB, behind a 255 MB site, with nothing set to ever expire them.
#
# This bucket does not need a rollback trail of its own, because every deploy
# rebuilds it from git: to roll back, revert the commit and let the deploy run.
# (Keeping versioning with a short expiry would also have stopped the growth,
# but it buys a rollback window that git already provides.)
#
# In Terraform, the many settings of an S3 bucket are split across several
# small, separate resources (versioning, encryption, public-access, etc.),
# each pointing back at the one bucket via its `bucket` argument. This is the
# versioning setting.
resource "aws_s3_bucket_versioning" "site" {
  # `.id` is the bucket's name, produced when the bucket resource is created.
  # Referencing it both targets the bucket AND tells Terraform to build the
  # bucket first, then this.
  bucket = aws_s3_bucket.site.id
  versioning_configuration {
    # "Suspended" makes a new upload replace the file in place instead of
    # keeping the old copy. It is the only way to switch versioning off: once
    # a bucket has ever been versioned, S3 can never make it unversioned again,
    # and "Disabled" (valid only for a bucket that never was) is rejected.
    # Suspending does not delete the copies already stored. The lifecycle rule
    # below does that.
    status = "Suspended"
  }
}

# A lifecycle configuration tells S3 to act on objects by age, on its own
# daily schedule: no script to run, and no charge for the deletes. This one
# keeps ONLY the current copy of each file. It clears the old versions stored
# while versioning was on, plus one last batch: the copies that were current at
# the moment of the switch become old versions the first time a deploy
# replaces them.
#
# Why a rule instead of a one-off delete script: when the deploy removes a
# page, a versioned bucket keeps its old copies and puts a "delete marker" on
# top to hide them. Delete the marker while old copies still sit underneath,
# which the obvious script does, and the removed page comes back online. This
# rule removes a marker only once nothing is left under it.
resource "aws_s3_bucket_lifecycle_configuration" "site" {
  # Apply these rules to the site bucket.
  bucket = aws_s3_bucket.site.id
  # The rules below act on old versions, so configure the versioning setting
  # first, then this.
  depends_on = [aws_s3_bucket_versioning.site]

  rule {
    # A label for the rule, shown in the S3 console.
    id = "keep-only-current-version"
    # Switches THIS rule on. (Nothing to do with bucket versioning, which is
    # the "Suspended" status above.)
    status = "Enabled"
    # An empty filter matches every object in the bucket.
    filter {}

    # A "noncurrent" version is an old copy that a newer upload replaced.
    # Delete each one a day after it was replaced, the shortest S3 allows.
    # S3 stops billing for a copy as soon as it qualifies, even if the actual
    # delete lands a little later.
    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    # Remove a delete marker once every old copy under it is gone, so a page
    # the deploy removed leaves nothing behind.
    expiration {
      expired_object_delete_marker = true
    }

    # Large uploads arrive in parts, and an interrupted one leaves invisible,
    # billed parts behind. Clear them after a day. Housekeeping: the site's
    # files are small, so there are normally none.
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# Belt-and-braces: even though the bucket policy below only grants
# CloudFront, block every public-access vector at the account-object level
# so a future careless ACL or policy edit can't silently expose the bucket.
resource "aws_s3_bucket_public_access_block" "site" {
  # Apply these guards to the site bucket.
  bucket = aws_s3_bucket.site.id
  # Reject any attempt to SET an ACL that grants public access.
  block_public_acls = true
  # Reject any bucket POLICY that would grant public access.
  block_public_policy = true
  # IGNORE any public-granting ACL that somehow already exists.
  ignore_public_acls = true
  # Even if a policy looks public, restrict access to authorized principals
  # only. With all four set to true, public exposure is effectively impossible.
  restrict_public_buckets = true
}

# Controls who "owns" objects and whether legacy ACLs are even allowed. An ACL
# (Access Control List) is S3's older, per-object permission mechanism; modern
# best practice is to disable ACLs entirely and grant access only through the
# bucket policy above. This resource enforces that.
resource "aws_s3_bucket_ownership_controls" "site" {
  # Apply to the site bucket.
  bucket = aws_s3_bucket.site.id
  rule {
    # "BucketOwnerEnforced" turns ACLs OFF: the bucket owner owns every object
    # and access is decided purely by IAM/bucket policy. Simpler and safer -
    # there is no ACL left that could accidentally widen access.
    object_ownership = "BucketOwnerEnforced" # ACLs disabled; policy-only access
  }
}

# Encrypt every object at rest. "Server-side encryption" means S3 scrambles
# the bytes on disk and unscrambles them on read, transparently. This is free,
# automatic, and what AWS already applies by default - declaring it explicitly
# keeps the intent visible and locked in as code.
resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  # Apply this encryption setting to the site bucket.
  bucket = aws_s3_bucket.site.id
  rule {
    apply_server_side_encryption_by_default {
      # AES256 = S3-managed keys (SSE-S3). No KMS key to manage or pay for,
      # which is plenty for a public static website that holds no secrets.
      sse_algorithm = "AES256"
    }
  }
}

# A "data source" (the `data` keyword) READS or COMPUTES something rather than
# creating a cloud object - the opposite of a `resource`. This particular data
# source is a helper that BUILDS an IAM policy document: instead of writing raw
# JSON by hand, we describe the rules in HCL and Terraform renders the JSON for
# us (referenced below as `.json`). IAM is AWS's permission system; a "bucket
# policy" is a set of permission rules attached directly to an S3 bucket.
#
# Bucket policy: allow ONLY this CloudFront distribution to read objects,
# scoped by the distribution ARN via the standard OAC source-arn condition.
# No principals, no public read.
data "aws_iam_policy_document" "site_bucket" {
  # Each `statement` is one permission rule. A policy can hold several; this
  # first one grants read access to the objects (files) in the bucket.
  statement {
    # `sid` (Statement ID) is just a human-readable label for this rule,
    # handy when reading the rendered policy in the AWS console.
    sid = "AllowCloudFrontOACRead"
    # `actions` lists the exact API operations allowed. s3:GetObject = download
    # an object. Granting only this (not write/delete) is "least privilege":
    # the caller can do nothing beyond what it strictly needs.
    actions = ["s3:GetObject"]
    # `resources` says WHICH objects the rule covers. `${...}` is Terraform
    # "interpolation" - it splices a value into a string. Here it inserts the
    # bucket's ARN (its unique AWS address) and appends `/*`, meaning "every
    # object inside this bucket".
    resources = ["${aws_s3_bucket.site.arn}/*"]

    # `principals` is WHO the rule applies to. Type "Service" plus the
    # identifier below means the AWS CloudFront service itself is the caller -
    # not a user or the public. This is how the bucket trusts CloudFront.
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    # A `condition` further narrows the rule so it only matches in specific
    # circumstances. Combined with the principal above, it is what makes the
    # access "ONLY this distribution" rather than "any CloudFront anywhere".
    condition {
      # How to compare: the request value must be exactly equal to a value
      # in the `values` list below.
      test = "StringEquals"
      # AWS:SourceArn is automatically set by CloudFront's OAC to the ARN of
      # the distribution making the request. (OAC = Origin Access Control, the
      # CloudFront feature that signs requests to S3; see cloudfront.tf.)
      variable = "AWS:SourceArn"
      # Require that SourceArn equal THIS distribution's ARN. Referencing
      # aws_cloudfront_distribution.site.arn also makes Terraform create the
      # distribution before this policy, since the policy depends on its ARN.
      values = [aws_cloudfront_distribution.site.arn]
    }
  }

  # Grant ListBucket as well so a request for a missing key returns a real
  # 404 from S3. Without it, a private bucket answers AccessDenied (403)
  # for absent objects, which would force every "page not found" through
  # the 403 error mapping and mask genuine 403s. Scoped to CloudFront only.
  statement {
    # Label for this second rule.
    sid = "AllowCloudFrontOACList"
    # s3:ListBucket = permission to look up whether a key exists in the bucket.
    actions = ["s3:ListBucket"]
    # Note: NO `/*` here. ListBucket acts on the bucket itself (its listing),
    # not on individual objects, so the resource is the bucket ARN alone.
    resources = [aws_s3_bucket.site.arn]

    # Same principal as above: only the CloudFront service may do this.
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    # Same source-ARN lock-down: only THIS distribution, via OAC, qualifies.
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

# This resource actually ATTACHES the policy above to the bucket. The data
# source merely *describes* the rules; nothing takes effect until a real
# aws_s3_bucket_policy object binds that JSON to the bucket in AWS.
resource "aws_s3_bucket_policy" "site" {
  # Which bucket to attach the policy to. `.id` is the bucket name, filled in
  # by AWS once aws_s3_bucket.site exists; referencing it here also tells
  # Terraform to create the bucket before this policy.
  bucket = aws_s3_bucket.site.id
  # The policy text itself. `.json` renders the data source above into the
  # exact JSON string AWS expects - we never hand-write that JSON.
  policy = data.aws_iam_policy_document.site_bucket.json
}
