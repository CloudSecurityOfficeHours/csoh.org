# Cloud Run runtime SA — least privilege. The container does no GCP API
# calls (it just serves static files), so this SA gets no roles. We still
# create a dedicated one rather than using the default Compute SA, because
# the default has overbroad project-editor-equivalent permissions.
resource "google_service_account" "cloud_run_runtime" {
  project      = var.project_id
  account_id   = "csoh-run-runtime"
  display_name = "csoh.org Cloud Run runtime SA"
  description  = "Identity the Cloud Run service runs as. No roles granted — static container only."
}

# Deploy SA — used by GitHub Actions via WIF. Only what's needed to push
# images and deploy revisions.
resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = "csoh-deployer"
  display_name = "csoh.org GitHub Actions deployer"
  description  = "Impersonated by GitHub Actions via WIF to push images and deploy Cloud Run revisions."
}

resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Required so the deployer can set the runtime SA on the Cloud Run service.
resource "google_service_account_iam_member" "deployer_act_as_runtime" {
  service_account_id = google_service_account.cloud_run_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# Narrow custom role: just the one permission needed to invalidate the
# Cloud CDN cache after a deploy. Predefined alternatives (loadBalancerAdmin,
# urlMapAdmin) include rights to *modify* the URL map and CDN policy, which
# the deployer has no business doing — those changes belong in Terraform.
resource "google_project_iam_custom_role" "cdn_cache_invalidator" {
  project     = var.project_id
  role_id     = "csohCdnCacheInvalidator"
  title       = "CSOH Cloud CDN Cache Invalidator"
  description = "Single permission needed to invalidate Cloud CDN entries after a Cloud Run deploy."
  permissions = ["compute.urlMaps.invalidateCache"]
}

resource "google_project_iam_member" "deployer_cdn_invalidator" {
  project = var.project_id
  role    = google_project_iam_custom_role.cdn_cache_invalidator.id
  member  = "serviceAccount:${google_service_account.deployer.email}"
}
