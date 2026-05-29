# --- What this file does ---
# It defines the Google Cloud (GCP) half of the website. The site is served
# from THREE clouds at once (AWS, GCP, Azure) behind one Cloudflare edge; on
# GCP the static site runs as a tiny web-server container on "Cloud Run".
# Cloud Run runs a container for you on demand and can scale all the way down
# to zero copies when no one is visiting (so it costs nothing while idle).
#
# Terraform concept: a "resource" block describes one real cloud object you
# want to exist. Terraform compares this description to what is actually in
# the cloud and creates/updates/deletes objects to match. The two strings
# after `resource` are (1) the resource TYPE and (2) a LOCAL NAME you pick.
# Here the type `google_cloud_run_v2_service` means "a Cloud Run service
# (v2 API)" and the local name `site` is how other lines in this Terraform
# code refer back to it (e.g. google_cloud_run_v2_service.site...).

# Cloud Run service. Image tag is overwritten on each deploy by GitHub
# Actions, so the lifecycle ignore_changes prevents Terraform from fighting
# the CI pipeline.
resource "google_cloud_run_v2_service" "site" {
  # Which GCP project this service lives in. `var.project_id` reads the
  # `project_id` input variable defined in variables.tf — `var.NAME` is how
  # Terraform pulls in a value so it isn't hard-coded in many places.
  project = var.project_id
  # The service's name within the project (shows up in the GCP console and in
  # its public *.run.app URL).
  name = "csoh-site"
  # The GCP region (data-center area) to run in, e.g. us-central1, taken from
  # the `region` input variable.
  location = var.region

  # "ingress" controls which networks are allowed to send requests to this
  # service. INGRESS_TRAFFIC_ALL means the public internet can reach it (as
  # opposed to internal-only). We need this because Cloudflare reaches this
  # service directly at its *.run.app URL from the outside (there is no GCP
  # load balancer anymore), so ingress must allow public traffic. Public
  # exposure is now gated at the Cloudflare edge (TLS, WAF, rate limiting,
  # Load Balancing) rather than by Cloud Armor on a GCLB.
  ingress = "INGRESS_TRAFFIC_ALL"

  # Service-level scaling. This is separate from `template.scaling` (which
  # configures per-revision auto-scaling). The Cloud Run v2 API populates
  # this block with default zeros on every service whether you declare it
  # or not — declaring it explicitly here keeps `terraform plan` clean
  # rather than showing a perpetual "remove this block" no-op diff.
  scaling {
    # Allow the service to scale down to 0 running copies when idle: cheapest
    # option, at the cost of a brief "cold start" on the first request after
    # idle. Fine here because Cloudflare caches pages and there are two other
    # always-available origins.
    min_instance_count = 0
  }

  # The "template" describes what each running copy (a "revision") looks
  # like: which identity it runs as, how it scales, and which container to
  # run. Editing this block makes Cloud Run roll out a new revision.
  template {
    # The identity (service account) the container runs as. We point at a
    # dedicated, no-permissions service account defined in service_accounts.tf
    # by referencing its `.email` attribute. Referencing one resource's
    # attribute from another (like this) also tells Terraform to create the
    # service account FIRST, then this service. The runtime SA intentionally
    # has zero roles because this container only serves static files and
    # never calls GCP APIs (least privilege: grant nothing it doesn't need).
    service_account = google_service_account.cloud_run_runtime.email

    # Per-revision auto-scaling: Cloud Run adds/removes copies based on
    # incoming traffic, between these bounds.
    scaling {
      # Can drop to 0 copies when there is no traffic (no cost while idle).
      min_instance_count = 0
      # Never run more than 10 copies, a safety cap on cost/runaway scaling.
      max_instance_count = 10
    }

    # Defines the actual container image and how it's run.
    containers {
      # The container image to run. This is just a stand-in Google "hello"
      # placeholder image; the real GitHub Actions deploy swaps in our own
      # image on first deploy. (The lifecycle block far below tells Terraform
      # to stop managing this field after creation so CI and Terraform don't
      # fight over it.)
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      # Which TCP port inside the container the web server listens on. Our
      # nginx container serves HTTP on port 80, so Cloud Run forwards
      # requests there.
      ports {
        container_port = 80
      }

      # CPU/memory each copy of the container is allowed to use.
      resources {
        # Upper bounds per copy: 1 vCPU and 256 MiB of RAM — plenty for
        # serving small static files.
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        # Only bill for CPU while a request is actually being handled, not
        # while a copy sits idle waiting (cheaper for bursty traffic).
        cpu_idle = true
        # Temporarily give extra CPU during container startup so cold starts
        # finish faster.
        startup_cpu_boost = true
      }

      # A "startup probe" is a health check Cloud Run runs while a new copy
      # is booting. Traffic is held back until the probe succeeds, so users
      # never hit a container that isn't ready yet.
      startup_probe {
        # Consider the container healthy once an HTTP GET to "/" on port 80
        # responds successfully.
        http_get {
          path = "/"
          port = 80
        }
        # Wait 1 second after the container starts before the first probe.
        initial_delay_seconds = 1
        # Re-check every 5 seconds.
        period_seconds = 5
        # Give up (mark the copy failed) after 3 consecutive failed checks.
        failure_threshold = 3
      }
    }
  }

  # "traffic" decides which revision(s) receive live requests. Cloud Run can
  # split traffic across revisions (handy for gradual rollouts); here we keep
  # it simple.
  traffic {
    # Always send traffic to the LATEST deployed revision...
    type = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    # ...and send 100% of it there (no canary/blue-green split).
    percent = 100
  }

  # "lifecycle" tweaks how Terraform manages this resource. `ignore_changes`
  # lists fields Terraform should set once at creation and then leave alone —
  # so it won't try to "fix" them back on later runs.
  lifecycle {
    ignore_changes = [
      # The container image is updated by the GitHub Actions deploy on every
      # release. Ignoring it stops Terraform from reverting it to the
      # placeholder image above. (The [0] indexing is just how you point at a
      # field inside these repeatable nested blocks.)
      template[0].containers[0].image,
      # `client`/`client_version` are metadata Cloud Run stamps with whatever
      # tool last deployed (e.g. gcloud). Ignoring them avoids noisy diffs
      # caused purely by the deploy tooling.
      client,
      client_version,
    ]
  }

  # "depends_on" forces an ordering: create these other resources BEFORE this
  # service. Terraform usually infers order from references, but here we make
  # the prerequisites explicit because the service won't work without them.
  depends_on = [
    # The required GCP APIs (like run.googleapis.com) must be enabled first —
    # defined in apis.tf.
    google_project_service.apis,
    # The Artifact Registry repo that will hold our container images must
    # exist first — defined in artifact_registry.tf.
    google_artifact_registry_repository.containers,
  ]
}

# GCP IAM concept: even though `ingress` (above) lets requests REACH the
# service over the network, Cloud Run also checks PERMISSION ("IAM") on each
# call. By default only authenticated callers with the run.invoker role may
# invoke it. This resource grants that role so anyone can call the service —
# i.e. it allows unauthenticated invocations so Cloudflare (and its
# health-check monitors) can reach the service at its *.run.app URL. The
# service is one of three interchangeable origins behind the Cloudflare Load
# Balancer; edge controls, not Cloud Run IAM, gate public exposure.
# An "IAM member" binding = "give this identity (member) this permission
# (role) on this object." Pairing a role with a member is the core of GCP
# access control.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  # Point this binding at the exact service created above by reading back its
  # project/location/name attributes (rather than retyping the values). This
  # also makes Terraform create the service first.
  project  = google_cloud_run_v2_service.site.project
  location = google_cloud_run_v2_service.site.location
  name     = google_cloud_run_v2_service.site.name
  # The permission being granted: run.invoker = "may send requests to this
  # Cloud Run service."
  role = "roles/run.invoker"
  # Who gets it: "allUsers" is GCP's special identity meaning everyone on the
  # internet, even unauthenticated. That's intentional here — the real
  # gatekeeping (TLS, WAF, rate limiting) happens at Cloudflare's edge.
  member = "allUsers"
}
