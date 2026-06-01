# Terraform is "infrastructure as code": instead of clicking around the
# Google Cloud console, we write the desired cloud setup in these .tf files
# and Terraform makes the real cloud match what we wrote. Every .tf file in
# this folder is read together as one configuration, so the order of files
# and blocks does not matter. This particular file holds the global,
# project-wide settings: which Terraform version to use, which "providers"
# (cloud plugins) are needed, where Terraform keeps its bookkeeping, and how
# those providers connect to Google Cloud.
#
# The "terraform {}" block configures Terraform itself (not any cloud
# resource). It is settings ABOUT the tool.
terraform {
  # Refuse to run unless the person's installed Terraform CLI is at least
  # version 1.6.0. ">=" means "this version or newer". This guards against
  # someone with an old Terraform accidentally corrupting things or hitting
  # features that did not exist yet.
  required_version = ">= 1.6.0"

  # A "provider" is a plugin that teaches Terraform how to talk to one
  # specific platform's API (here, Google Cloud). "required_providers" lists
  # every provider this configuration needs, where to download it from, and
  # which versions are acceptable. Terraform fetches these automatically on
  # "terraform init".
  required_providers {
    # The main Google Cloud provider. "google" is the local nickname we use
    # to refer to it in provider/resource blocks below (e.g. resources named
    # "google_service_account"). "source" is its address in the public
    # Terraform Registry: the "hashicorp" namespace, package "google".
    google = {
      source = "hashicorp/google"
      # Version constraint. "~>" is the "pessimistic" operator: "~> 6.0"
      # means "any 6.x release (6.0, 6.1, 6.7, ...) but NOT 7.0". This lets
      # us pick up bug fixes within the v6 line while blocking a major
      # upgrade that could introduce breaking changes without our review.
      version = "~> 6.0"
    }
    # The "google-beta" provider exposes Google Cloud features that are still
    # in beta / preview and not yet in the stable "google" provider. It is a
    # separate plugin, so it must be declared separately even though it
    # mirrors the same cloud. Resources that need a beta-only feature set
    # "provider = google-beta" to use this one instead of the stable one.
    google-beta = {
      source = "hashicorp/google-beta"
      # Kept on the same major line as the stable provider so the two stay
      # compatible with each other.
      version = "~> 6.0"
    }
  }

  # Terraform records what it has built in a "state file" - a JSON inventory
  # mapping each resource in these .tf files to the real cloud object it
  # created (IDs, settings, etc.). The "backend" decides WHERE that state
  # file lives. "gcs" means store it in a Google Cloud Storage bucket
  # (Google's object storage, like AWS S3) instead of on one laptop. A
  # shared remote backend lets CI and every teammate read/write the same
  # state and prevents two runs from clobbering each other.
  backend "gcs" {
    # The Cloud Storage bucket that holds the state file. This bucket is
    # created/managed outside this config (a "bootstrap" step) - a backend
    # cannot store its own state, so the bucket must already exist before
    # "terraform init" can use it.
    bucket = "csoh-org-495800-tfstate"
    # A path prefix (like a folder) inside that bucket. Using "csoh/prod"
    # keeps this production environment's state neatly separated from any
    # other environments or projects that might share the same bucket.
    prefix = "csoh/prod"
  }
}

# Having DECLARED the provider above, we now CONFIGURE it. This block sets
# the defaults that the google provider applies to every resource it
# manages, so we do not repeat them on each resource. (How Terraform actually
# logs in to Google is NOT set here: in CI it comes from the short-lived
# OIDC credentials that GitHub Actions obtains via Workload Identity
# Federation - see wif.tf - so no long-lived key sits in this file.)
provider "google" {
  # The Google Cloud project these resources live in. "var.project_id" reads
  # the value of the "project_id" variable (defined in variables.tf,
  # defaulting to "csoh-org-495800"). "var.<name>" is how Terraform
  # references a variable; pulling it from a variable keeps the project ID in
  # one place instead of hard-coded across many files.
  project = var.project_id
  # The default region (a geographic location of Google data centers, e.g.
  # "us-central1") for regional resources like Cloud Run and Artifact
  # Registry. Also sourced from a variable so it is easy to change in one
  # spot.
  region = var.region
}

# The matching configuration for the beta provider. It must be configured
# separately even though the values are identical, because it is a distinct
# plugin. Resources that opt in with "provider = google-beta" pick up these
# settings.
provider "google-beta" {
  project = var.project_id
  region  = var.region
}
