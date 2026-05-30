# AWS origin for csoh.org — private S3 bucket served over HTTPS by
# CloudFront, fronted (like all three origins) by Cloudflare.
#
# State lives in the SAME GCS bucket as the GCP stack, under a separate
# prefix. We deliberately keep one state store across all clouds rather
# than bootstrapping a state bucket in each provider: it's one thing to
# secure, the bucket already exists, and storage cost is pennies. The
# trade-off — Terraform needs GCS application-default creds present when
# running the AWS dir — is acceptable for a solo-maintained repo.
# The `terraform {}` block configures Terraform ITSELF (not any cloud).
# It pins tool/provider versions and says where state is stored, so every
# machine and CI run behaves identically. A "provider" is the plugin that
# lets Terraform talk to a specific platform's API (here, AWS).
terraform {
  # Refuse to run on Terraform older than 1.6.0. This guards against an old
  # CLI silently misreading newer syntax in these files.
  required_version = ">= 1.6.0"

  # Declares which provider plugins this stack needs and where to get them.
  # Terraform downloads them on `terraform init`.
  required_providers {
    # The AWS provider. `source` is its address in the public registry
    # (registry.terraform.io/hashicorp/aws).
    aws = {
      source = "hashicorp/aws"
      # `~> 5.0` is a "pessimistic" version constraint: allow any 5.x
      # (5.1, 5.40, ...) but NOT 6.0. This picks up bug fixes while
      # avoiding the breaking changes a major-version bump can bring.
      version = "~> 5.0"
    }
  }

  # The "backend" is WHERE Terraform stores its state file — the JSON record
  # mapping the resources in this code to the real cloud objects it created.
  # State must be shared/remote so CI and humans don't fight over local copies.
  # `gcs` = Google Cloud Storage. Note: this AWS stack deliberately keeps its
  # state in a GCS bucket (the same one the GCP stack uses), per the rationale
  # at the top of this file — one state store to secure instead of one per cloud.
  backend "gcs" {
    # The existing GCS bucket that holds all of this repo's Terraform state.
    bucket = "csoh-org-495800-tfstate"
    # A folder-like key prefix inside that bucket. Each stack uses its own
    # prefix so their state files never collide (compare the GCP stack's
    # `csoh/prod`).
    prefix = "csoh/aws"
  }
}

# Configures the AWS provider declared above: the credentials/region context
# every AWS resource in this stack is created under. Credentials are NOT set
# here — they arrive from the environment (locally your AWS profile; in CI a
# short-lived OIDC token), which is why no secrets appear in this file.
provider "aws" {
  # `var.X` reads an input variable (defined in variables.tf). This is
  # Terraform's interpolation/reference syntax — values flow between files
  # instead of being hard-coded. Here, the region for region-scoped resources
  # like the S3 bucket (default: us-east-1).
  region = var.aws_region
  # A safety guardrail: Terraform aborts if the active credentials belong to
  # any account other than this one. Prevents an `apply` with the wrong
  # profile or stale creds from touching the wrong AWS account. The `[...]`
  # makes a one-element list, the type this argument expects.
  allowed_account_ids = [var.aws_account_id]

  # `default_tags` automatically stamps these key/value tags onto every
  # taggable AWS resource this provider creates — no need to repeat them on
  # each resource. Tags are metadata used for cost tracking, search, and
  # knowing at a glance what created a resource.
  default_tags {
    tags = {
      # Which project this belongs to.
      project = "csoh.org"
      # Signals these resources are managed by Terraform — don't hand-edit
      # them in the AWS console, or you'll drift from the code.
      managedBy = "terraform"
      # Which part of the system: this stack is the static-site origin.
      component = "static-origin"
    }
  }
}
