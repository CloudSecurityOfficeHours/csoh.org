# --- What this file does ---
# Pull request previews. Every open pull request from a branch in this repo
# gets its own URL on Cloud Run, built from the PR's head commit, and the URL
# goes away when the PR is approved, gets a changes-requested review, or is
# closed. .github/workflows/pr-preview.yml drives it; this file holds the
# cloud side.
#
# The shape: ONE Cloud Run service, csoh-site-preview, and one *revision tag*
# per pull request. A revision tag gives a single revision its own hostname
# (pr-123---csoh-site-preview-<hash>.a.run.app) without sending it any
# of the service's main traffic. Deploying a PR is "add a revision with no
# traffic and tag it pr-<n>"; removing the preview is "drop the tag, then
# delete revisions nothing points at".
#
# Why one shared service rather than a service per PR: Cloud Run IAM can be
# granted on a single service, which is exactly how the QA deployer is scoped
# (service_accounts.tf). A service per PR would need run.admin across the
# whole project, which includes the production csoh-site service. One service
# keeps the preview identity unable to touch production or QA, with no IAM
# Conditions involved.
#
# Why a separate Artifact Registry repo: the csoh-containers repo has mutable
# tags, and production deploys whatever an existing csoh-site:<sha> tag
# resolves to. Write access there would let a pull request job overwrite a tag
# that QA or production later reuses. Preview images therefore live in
# csoh-previews, and the preview identity can write nowhere else.
#
# Nothing here is promoted. QA_PIPELINE_README.md's rule that QA and
# production images must stay identical does not extend to previews: the
# preview workflow rewrites robots.txt before building, so the image differs on
# purpose and must never be pushed to csoh-containers.

# ---------------------------------------------------------------------------
# Image repository for preview builds only.
# ---------------------------------------------------------------------------
resource "google_artifact_registry_repository" "previews" {
  project       = var.project_id
  location      = var.region
  repository_id = "csoh-previews"
  description   = "Pull request preview images. Never deployed to production or QA."
  format        = "DOCKER"

  docker_config {
    immutable_tags = false
  }

  # Preview images are disposable. A tagged revision keeps serving after its
  # image is gone only while an instance is warm, so the window is long enough
  # to outlast any pull request that is still being worked on, and the daily
  # sweep in pr-preview.yml removes the tag long before then for closed ones.
  cleanup_policies {
    id     = "delete-after-30d"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "2592000s" # 30d
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# The preview service. Configured like site_qa so a preview exercises the same
# nginx serving path, with a lower instance cap.
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "site_preview" {
  project  = var.project_id
  name     = "csoh-site-preview"
  location = var.region

  ingress = "INGRESS_TRAFFIC_ALL"

  binary_authorization {
    use_default = true
  }

  scaling {
    min_instance_count = 0
  }

  template {
    service_account = google_service_account.cloud_run_runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      # Placeholder. The service's main URL keeps serving this; previews are
      # reached only through their pr-<n> tag URLs.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 80
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        http_get {
          path = "/"
          port = 80
        }
        initial_delay_seconds = 1
        period_seconds        = 5
        failure_threshold     = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    # The workflow owns both of these. Each PR deploy replaces the template
    # image, and `gcloud run deploy --no-traffic --tag` rewrites the traffic
    # block: it pins the main traffic to the revision that was serving and adds
    # one zero-percent tagged entry per open PR. Without ignoring `traffic`, the
    # next apply would strip every preview tag.
    ignore_changes = [
      template[0].containers[0].image,
      traffic,
      client,
      client_version,
    ]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.previews,
  ]
}

# Previews are public, the same as the QA and production *.run.app origins.
# Only branches in this repo get a preview, so the content comes from people
# who already have write access.
resource "google_cloud_run_v2_service_iam_member" "public_invoker_preview" {
  project  = google_cloud_run_v2_service.site_preview.project
  location = google_cloud_run_v2_service.site_preview.location
  name     = google_cloud_run_v2_service.site_preview.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# The preview deploy identity. Same pattern as csoh-deployer-qa, pointed at
# the preview service and the preview image repo.
# ---------------------------------------------------------------------------
resource "google_service_account" "deployer_preview" {
  project      = var.project_id
  account_id   = "csoh-deployer-preview"
  display_name = "csoh.org GitHub Actions PR preview deployer"
  description  = "Impersonated by pr-preview.yml via WIF to manage revision tags on csoh-site-preview only."
}

# run.admin on the one service: deploy revisions, add and remove tags, delete
# revisions. Nothing outside csoh-site-preview.
resource "google_cloud_run_v2_service_iam_member" "deployer_preview_run_admin" {
  project  = google_cloud_run_v2_service.site_preview.project
  location = google_cloud_run_v2_service.site_preview.location
  name     = google_cloud_run_v2_service.site_preview.name
  role     = "roles/run.admin"
  member   = "serviceAccount:${google_service_account.deployer_preview.email}"
}

# Read-only, project wide. gcloud polls operations and lists revisions through
# project-level endpoints that a service-scoped grant does not cover; the QA
# deployer needs the same grant for the same reason.
resource "google_project_iam_member" "deployer_preview_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.deployer_preview.email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_preview_ar_writer" {
  project    = google_artifact_registry_repository.previews.project
  location   = google_artifact_registry_repository.previews.location
  repository = google_artifact_registry_repository.previews.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer_preview.email}"
}

# Lets the deployer start revisions that run as the role-less runtime SA.
resource "google_service_account_iam_member" "deployer_preview_act_as_runtime" {
  service_account_id = google_service_account.cloud_run_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer_preview.email}"
}

# Trust for jobs that declare `environment: pr-preview`, bound to this SA only.
# The pool-wide gate is the attribute_condition in wif.tf, which must list the
# same subject.
resource "google_service_account_iam_member" "deployer_preview_wif_binding" {
  service_account_id = google_service_account.deployer_preview.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principal://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/subject/repo:${var.github_owner}/${var.github_repo}:environment:pr-preview"
}
