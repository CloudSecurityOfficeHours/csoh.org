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

# (Removed: the csohCdnCacheInvalidator custom role. It existed only to let
# the deployer invalidate the Cloud CDN cache after a deploy. With the GCLB
# and Cloud CDN retired, there is nothing to invalidate — Cloudflare caches
# at the edge and is purged separately. The deployer now needs only
# run.admin + artifactregistry.writer + act-as on the runtime SA.)
