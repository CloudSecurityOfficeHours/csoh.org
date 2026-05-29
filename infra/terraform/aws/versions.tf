# AWS origin for csoh.org — private S3 bucket served over HTTPS by
# CloudFront, fronted (like all three origins) by Cloudflare.
#
# State lives in the SAME GCS bucket as the GCP stack, under a separate
# prefix. We deliberately keep one state store across all clouds rather
# than bootstrapping a state bucket in each provider: it's one thing to
# secure, the bucket already exists, and storage cost is pennies. The
# trade-off — Terraform needs GCS application-default creds present when
# running the AWS dir — is acceptable for a solo-maintained repo.
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "csoh-org-495800-tfstate"
    prefix = "csoh/aws"
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = {
      project   = "csoh.org"
      managedBy = "terraform"
      component = "static-origin"
    }
  }
}
