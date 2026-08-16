# --- What this file does ---
# It creates the GCP "identities" (service accounts) and grants them the
# permissions this project needs - nothing more. There are two identities:
#   1. cloud_run_runtime - WHO the website container runs AS while it serves
#      pages (see template.service_account in cloud_run.tf).
#   2. deployer - WHO GitHub Actions becomes during a deploy to push the new
#      container image and roll out a new Cloud Run revision.
#
# Key cloud idea: a SERVICE ACCOUNT is a non-human identity (a "robot user")
# that programs/services log in as, instead of a person. Like a human user it
# has an email-style name and can be granted permissions. In GCP you almost
# never hand out permissions to a program directly - you create a service
# account, give the program that identity, and grant the account roles.
#
# Key security idea this whole file follows: LEAST PRIVILEGE - give each
# identity only the exact permissions it needs and no more. If credentials
# ever leak, the blast radius is limited to those few permissions.
#
# Terraform concept: a `provider` is the plugin that knows how to talk to a
# specific cloud's API. The Google provider used by every resource here is
# declared once in versions.tf (`hashicorp/google`), so it is NOT repeated in
# this file - Terraform applies it automatically to every `google_*` resource.
#
# Terraform concept: a `resource` block describes one real cloud object you
# want to exist (contrast a `data` source, which only READS something that
# already exists - there are none in this file). The two strings after
# `resource` are the resource TYPE (e.g. `google_service_account`) and a LOCAL
# NAME you pick (e.g. `cloud_run_runtime`); other lines refer back to it as
# `google_service_account.cloud_run_runtime`.
#
# Cloud Run runtime SA - least privilege. The container does no GCP API
# calls (it just serves static files), so this SA gets no roles. We still
# create a dedicated one rather than using the default Compute SA, because
# the default has overbroad project-editor-equivalent permissions.
resource "google_service_account" "cloud_run_runtime" {
  # Which GCP project this identity belongs to. `var.project_id` reads the
  # `project_id` input variable (defined in variables.tf) - `var.NAME` is how
  # Terraform pulls in a value so it isn't hard-coded in many places.
  project = var.project_id
  # The short, unique ID for the account. GCP turns this into the account's
  # full login name (its email), which always looks like
  # <account_id>@<project_id>.iam.gserviceaccount.com - here
  # csoh-run-runtime@csoh-org-495800.iam.gserviceaccount.com.
  account_id = "csoh-run-runtime"
  # A friendly, human-readable label shown in the GCP console. Purely cosmetic.
  display_name = "csoh.org Cloud Run runtime SA"
  # Free-text note explaining what this account is for. Purely informational.
  description = "Identity the Cloud Run service runs as. No roles granted - static container only."
}

# Deploy SA - used by GitHub Actions via WIF. Only what's needed to push
# images and deploy revisions.
#
# WIF = Workload Identity Federation (configured in wif.tf). It lets the
# GitHub Actions deploy job briefly "impersonate" (act as) this service
# account WITHOUT any stored password or downloaded key file: GitHub hands
# GCP a short-lived signed OIDC token proving "this is a workflow run from the
# csoh.org repo", and GCP trades it for a temporary access token for this
# account. Keyless auth means there is no long-lived secret that could leak.
resource "google_service_account" "deployer" {
  # Same project as everything else (from the project_id variable).
  project = var.project_id
  # ID -> email csoh-deployer@csoh-org-495800.iam.gserviceaccount.com.
  account_id = "csoh-deployer"
  # Human-readable label in the console.
  display_name = "csoh.org GitHub Actions deployer"
  # Note describing the account's purpose.
  description = "Impersonated by GitHub Actions via WIF to push images and deploy Cloud Run revisions."
}

# GCP permissions work as IAM bindings: "grant MEMBER (an identity) this ROLE
# (a named bundle of permissions) on this SCOPE (here, the whole project)".
# `google_project_iam_member` adds ONE such binding at the project level
# without disturbing any other bindings (additive and non-destructive - unlike
# `google_project_iam_policy`, which would overwrite the project's entire
# policy). Each binding the deployer needs is its own small resource so the
# grant is explicit and auditable.
#
# This binding lets the deployer manage Cloud Run. `roles/run.admin` is a
# predefined GCP role (`roles/...` = built-in, maintained by Google) that
# bundles the permissions to create/update Cloud Run services and roll out new
# revisions - exactly what CI does on each deploy.
resource "google_project_iam_member" "deployer_run_admin" {
  # The scope of the grant: the whole project.
  project = var.project_id
  # The bundle of permissions being granted.
  role = "roles/run.admin"
  # WHO receives the role. IAM members must carry a TYPE prefix so GCP knows
  # what kind of identity this is (`serviceAccount:`, `user:`, `group:`,
  # `allUsers`, ...). `${...}` is Terraform's interpolation: it splices a value
  # into the surrounding string - here the deployer account's email, READ from
  # the resource above (`google_service_account.deployer.email`). Referencing
  # one resource's attribute from another like this also tells Terraform the
  # deployer SA must be created FIRST, so it orders the work automatically.
  member = "serviceAccount:${google_service_account.deployer.email}"
}

# Second deployer binding: permission to PUSH container images into Artifact
# Registry (the private image repo defined in artifact_registry.tf). On each
# deploy CI builds the nginx image and uploads it here before telling Cloud
# Run to use it. `roles/artifactregistry.writer` grants push (upload) rights
# - deliberately NOT the broader admin role, keeping to least privilege.
resource "google_project_iam_member" "deployer_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Required so the deployer can set the runtime SA on the Cloud Run service.
#
# Subtlety: in GCP, to deploy a service that RUNS AS some identity, the
# deployer must be allowed to "act as" (use) that identity - otherwise it
# could sneak a service into running with an account it doesn't control. This
# binding grants exactly that one capability. Note the resource type is
# `google_service_account_iam_member` (not `google_project_iam_member` above):
# the grant is scoped to a SINGLE service account, not the whole project - so
# the deployer can act as ONLY the runtime SA, nothing else. Tight scoping is
# least privilege again.
resource "google_service_account_iam_member" "deployer_act_as_runtime" {
  # WHICH service account this grant is attached to: the runtime SA. `.name`
  # is its full resource path (projects/.../serviceAccounts/<email>), which is
  # the identifier this argument expects. Referencing it also makes Terraform
  # create the runtime SA before this binding.
  service_account_id = google_service_account.cloud_run_runtime.name
  # The "act as / use this service account" permission bundle.
  role = "roles/iam.serviceAccountUser"
  # WHO gets it: the deployer SA (same `serviceAccount:` + interpolation
  # pattern as the project bindings above).
  member = "serviceAccount:${google_service_account.deployer.email}"
}

# (Removed: the csohCdnCacheInvalidator custom role. It existed only to let
# the deployer invalidate the Cloud CDN cache after a deploy. With the GCLB
# and Cloud CDN retired, there is nothing to invalidate - Cloudflare caches
# at the edge and is purged separately. The deployer now needs only
# run.admin + artifactregistry.writer + act-as on the runtime SA.)

# --- The QA deployer ----------------------------------------------------------
# A THIRD identity, impersonated by the deploy-qa.yml workflow when it ships the
# `qa` branch to the csoh-site-qa Cloud Run service.
#
# WHY NOT JUST REUSE THE DEPLOYER ABOVE. Because that one holds `roles/run.admin`
# at PROJECT scope, so anything able to impersonate it can deploy an arbitrary
# image to the production service. Reusing it would mean the QA path - which
# runs on a branch with no review requirement, and which exists precisely so
# half-finished work can be pushed to it - could ship straight to csoh.org. The
# bindings below are deliberately narrower: this account can update exactly one
# Cloud Run service, and that service is not production.
#
# Note what this does NOT isolate, because it is easy to over-read. QA and
# production share one Artifact Registry repo (on purpose - it is what makes
# promoting a tested image possible rather than rebuilding it), so an image
# pushed by QA is an image production may later run. That is inherent to the
# promotion model and is gated by the human merge to `main`, the validate job,
# and the Trivy scan, not by this identity split. What the split buys is that a
# compromised QA workflow cannot *deploy* to production - it can only offer
# bytes that a later, separately-gated production run chooses to pick up.
resource "google_service_account" "deployer_qa" {
  project = var.project_id
  # ID -> email csoh-deployer-qa@csoh-org-495800.iam.gserviceaccount.com.
  account_id   = "csoh-deployer-qa"
  display_name = "csoh.org GitHub Actions QA deployer"
  description  = "Impersonated by deploy-qa.yml via WIF to deploy the csoh-site-qa Cloud Run service only."
}

# Grant 1 of 4: admin, but ONLY on the QA service.
#
# Contrast `google_project_iam_member.deployer_run_admin` above, which grants
# the same role across the entire project. This resource type
# (`google_cloud_run_v2_service_iam_member`) attaches the binding to ONE named
# Cloud Run service, so the role's power to create revisions and change traffic
# splits stops at csoh-site-qa. Referencing the service's attributes rather than
# retyping its name also makes Terraform create it first.
resource "google_cloud_run_v2_service_iam_member" "deployer_qa_run_admin" {
  project  = google_cloud_run_v2_service.site_qa.project
  location = google_cloud_run_v2_service.site_qa.location
  name     = google_cloud_run_v2_service.site_qa.name
  role     = "roles/run.admin"
  member   = "serviceAccount:${google_service_account.deployer_qa.email}"
}

# Grant 2 of 4: project-wide READ on Cloud Run.
#
# This one is project-scoped where grant 1 is not, so it deserves a word.
# `gcloud run deploy` does more than update the service: it resolves the
# service, then polls a long-running operation until the revision is ready.
# Those reads are not all scoped to the service being deployed, so a
# service-only binding leaves the deploy failing partway through with a
# permission error that names an operation rather than the service.
# `roles/run.viewer` is READ-ONLY - it can list and describe services and
# operations and cannot mutate anything - so widening this one to the project
# costs no ability to change production, which grant 1 is what withholds.
resource "google_project_iam_member" "deployer_qa_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.deployer_qa.email}"
}

# Grant 3 of 4: push images, scoped to the one repository.
#
# The production deployer holds `roles/artifactregistry.writer` at project
# scope (see above); this uses the repository-scoped resource type instead, so
# the QA identity can write to csoh-containers and to no other repo that may
# exist in this project later. Same role, tighter blast radius.
resource "google_artifact_registry_repository_iam_member" "deployer_qa_ar_writer" {
  project    = google_artifact_registry_repository.containers.project
  location   = google_artifact_registry_repository.containers.location
  repository = google_artifact_registry_repository.containers.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer_qa.email}"
}

# Grant 4 of 4: permission to act as the runtime identity.
#
# Same requirement, and same single-service-account scoping, as
# `deployer_act_as_runtime` above: to deploy a service that RUNS AS the runtime
# SA, the deployer must be allowed to use that SA. Both Cloud Run services run
# as the same zero-role runtime account, so this points at the same target.
resource "google_service_account_iam_member" "deployer_qa_act_as_runtime" {
  service_account_id = google_service_account.cloud_run_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer_qa.email}"
}
