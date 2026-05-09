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

variable "staging_domain" {
  description = "Staging hostname (separate Cloudflare record) for verifying GCP path before cutover"
  type        = string
  default     = "gcp.csoh.org"
}

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
