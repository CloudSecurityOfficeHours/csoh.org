# Cloud Run service. Image tag is overwritten on each deploy by GitHub
# Actions, so the lifecycle ignore_changes prevents Terraform from fighting
# the CI pipeline.
resource "google_cloud_run_v2_service" "site" {
  project  = var.project_id
  name     = "csoh-site"
  location = var.region

  # Cloudflare reaches this service directly at its *.run.app URL (there is
  # no GCP load balancer anymore), so ingress must allow public traffic.
  # Public exposure is now gated at the Cloudflare edge (TLS, WAF, rate
  # limiting, Load Balancing) rather than by Cloud Armor on a GCLB.
  ingress = "INGRESS_TRAFFIC_ALL"

  # Service-level scaling. This is separate from `template.scaling` (which
  # configures per-revision auto-scaling). The Cloud Run v2 API populates
  # this block with default zeros on every service whether you declare it
  # or not — declaring it explicitly here keeps `terraform plan` clean
  # rather than showing a perpetual "remove this block" no-op diff.
  scaling {
    min_instance_count = 0
  }

  template {
    service_account = google_service_account.cloud_run_runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      # Placeholder image. CI replaces this on first deploy.
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
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.containers,
  ]
}

# Allow unauthenticated invocations so Cloudflare (and its health-check
# monitors) can reach the service at its *.run.app URL. The service is one
# of three interchangeable origins behind the Cloudflare Load Balancer;
# edge controls, not Cloud Run IAM, gate public exposure.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = google_cloud_run_v2_service.site.project
  location = google_cloud_run_v2_service.site.location
  name     = google_cloud_run_v2_service.site.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
