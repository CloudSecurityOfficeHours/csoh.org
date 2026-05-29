variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "csoh-org-495800"
}

variable "project_number" {
  description = "GCP project number (used for WIF principal)"
  type        = string
  default     = "23727240440"
}

variable "region" {
  description = "Primary region for Cloud Run + Artifact Registry"
  type        = string
  default     = "us-central1"
}

variable "domain" {
  description = "Production domain"
  type        = string
  default     = "csoh.org"
}

# (Removed: staging_domain. It only fed the GCP managed SSL cert on the
# now-retired load balancer. Cloudflare terminates TLS at the edge and
# reaches Cloud Run at its *.run.app hostname, which already has a valid
# Google cert — no GCP-managed cert, and no staging hostname, required.)

variable "github_owner" {
  description = "GitHub org/user that owns the repo"
  type        = string
  default     = "CloudSecurityOfficeHours"
}

variable "github_repo" {
  description = "GitHub repo name"
  type        = string
  default     = "csoh.org"
}

variable "github_branch" {
  description = "Branch authorized to deploy via WIF"
  type        = string
  default     = "main"
}
