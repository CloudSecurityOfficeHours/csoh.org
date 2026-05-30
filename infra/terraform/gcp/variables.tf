# --- What this file does ---
# This file declares the INPUT VARIABLES for the GCP half of the website.
# Think of a Terraform "variable" as a named setting (like a function
# argument): you define it once here, then the other .tf files in this folder
# read its value with the syntax `var.NAME` (for example `var.project_id`).
# Keeping these values in one place means you change a setting here instead of
# hunting for the same string copy-pasted across many files.
#
# Each `variable` block can declare three things we use below:
#   - description : a human note explaining what the value is for.
#   - type        : the kind of value allowed. `string` means ordinary text.
#   - default     : the value used when no one passes another one in. Because
#                   every variable here has a default, this configuration runs
#                   without anyone having to supply values by hand.
# None of these are marked `sensitive`, because they are all public, non-secret
# identifiers (project IDs, repo names, a domain) — there are no passwords or
# keys here. (Keyless deploys via OIDC are exactly why no secrets are needed.)

# The GCP "project" is the top-level container that owns and bills for all the
# Google Cloud resources in this folder (the Cloud Run service, its container
# registry, the deploy identity, etc.). Every resource must say which project
# it belongs to, so almost every other file references `var.project_id`. The
# trailing number in the default is auto-assigned by Google when the project
# is created and makes the ID globally unique.
variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "csoh-org-495800"
}

# The project NUMBER is a second, numeric ID for the same project (the
# `project_id` above is the human-readable text name; this is its numeric
# twin). Some Google APIs insist on the number rather than the text ID. Here
# it is needed to build the long "principalSet://..." identifier in wif.tf
# that names exactly which GitHub repo is allowed to log in — Workload
# Identity Federation (WIF) is GCP's way of letting an outside system like
# GitHub Actions authenticate WITHOUT a stored password or key file.
variable "project_number" {
  description = "GCP project number (used for WIF principal)"
  type        = string
  default     = "23727240440"
}

# A GCP "region" is a geographic cluster of data centers (here `us-central1`,
# in Iowa). Resources live in a region, and you generally want related ones in
# the SAME region for low latency and so they can talk cheaply. This value
# tells both the Cloud Run service (cloud_run.tf) and the Artifact Registry
# container repository (artifact_registry.tf) where to live, and is also fed
# to the `google` providers in versions.tf as their default location.
variable "region" {
  description = "Primary region for Cloud Run + Artifact Registry"
  type        = string
  default     = "us-central1"
}

# The public website address visitors type into their browser. On GCP this is
# mostly informational (Cloudflare owns the real domain at the edge and
# forwards traffic to Cloud Run's built-in *.run.app URL), but it is handy to
# have on hand — for example the uptime/monitoring checks in monitoring.tf
# reference the site by this name.
variable "domain" {
  description = "Production domain"
  type        = string
  default     = "csoh.org"
}

# (Removed: staging_domain. It only fed the GCP managed SSL cert on the
# now-retired load balancer. Cloudflare terminates TLS at the edge and
# reaches Cloud Run at its *.run.app hostname, which already has a valid
# Google cert — no GCP-managed cert, and no staging hostname, required.)

# The next three variables together pin down EXACTLY which GitHub repository
# and branch are trusted to deploy this site, with no stored credentials. They
# are stitched into the WIF rules in wif.tf: when a GitHub Actions run asks GCP
# for access, GCP checks the run's identity token (its "claims") against these
# values and only hands back a short-lived token if they match. This is the
# heart of "least privilege" + "keyless" auth — only the right repo/branch,
# nothing else, can ever act as the deployer identity.

# Which GitHub account (organization or user) owns the repo. Combined with
# `github_repo` below, it forms the full "owner/repo" string that wif.tf
# requires every incoming token to carry, so a workflow in some OTHER repo
# cannot mint a token for this project.
variable "github_owner" {
  description = "GitHub org/user that owns the repo"
  type        = string
  default     = "CloudSecurityOfficeHours"
}

# The repository's own name (the part after the slash in "owner/repo"). Paired
# with `github_owner` above to identify the one allowed source repo.
variable "github_repo" {
  description = "GitHub repo name"
  type        = string
  default     = "csoh.org"
}

# The single git branch (here `main`) that is meant to perform real deploys,
# so a push to a random feature branch can't ship to production. The branch
# name a workflow runs on is one of the token claims WIF maps in wif.tf, which
# is what makes restricting deploys to this branch possible.
variable "github_branch" {
  description = "Branch authorized to deploy via WIF"
  type        = string
  default     = "main"
}
