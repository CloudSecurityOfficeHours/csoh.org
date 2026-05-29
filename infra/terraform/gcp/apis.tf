# APIs the project needs. disable_on_destroy=false so `terraform destroy`
# doesn't break other resources still using these services.
locals {
  # Trimmed after retiring the GCLB: compute (LB resources),
  # certificatemanager + dns (GCP managed cert) are no longer used now that
  # Cloud Run is a direct Cloudflare origin.
  required_apis = [
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbuild.googleapis.com",
    "containeranalysis.googleapis.com",
    "binaryauthorization.googleapis.com",
    "containerscanning.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
