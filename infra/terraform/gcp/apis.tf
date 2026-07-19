# In Google Cloud, every service (Cloud Run, logging, etc.) is fronted by an
# "API" that must be explicitly turned ON for a project before you can use it.
# A brand-new project has almost everything disabled, so this file's job is to
# enable exactly the APIs csoh.org depends on - and nothing more (least
# privilege: a smaller enabled surface is a smaller attack surface).
# A `locals` block defines named values local to this Terraform configuration.
# Think of them as constants you can reference elsewhere as `local.<name>`.
# They reduce repetition and give a meaningful name to a value (here, the list
# of API service identifiers we want enabled).
locals {
  # Trimmed after retiring the GCLB: compute (LB resources),
  # certificatemanager + dns (GCP managed cert) are no longer used now that
  # Cloud Run is a direct Cloudflare origin.
  # Each string below is the unique "service name" Google uses to identify an
  # API. Enabling it is the equivalent of flipping the "Enable API" switch in
  # the Cloud Console. The list is iterated over by the resource further down.
  required_apis = [
    # Artifact Registry: the private Docker image repository where CI pushes
    # the nginx container image. Cloud Run pulls the image from here.
    "artifactregistry.googleapis.com",
    # Cloud Run: the serverless platform that runs the nginx container which
    # serves the static site (this is csoh.org's GCP origin behind Cloudflare).
    "run.googleapis.com",
    # IAM (Identity and Access Management): the service that manages "who can
    # do what" - service accounts and their roles/permissions.
    "iam.googleapis.com",
    # IAM Credentials: needed to mint short-lived tokens and impersonate
    # service accounts (used by Workload Identity Federation, see wif.tf).
    "iamcredentials.googleapis.com",
    # Security Token Service (STS): exchanges an external OIDC token (the one
    # GitHub Actions presents) for a temporary Google credential - the core of
    # keyless, no-stored-secrets deploys.
    "sts.googleapis.com",
    # Cloud Resource Manager: lets Terraform read/manage project-level settings
    # such as IAM policy. Many other APIs depend on it being enabled.
    "cloudresourcemanager.googleapis.com",
    # Cloud Logging: collects logs from Cloud Run and other services.
    "logging.googleapis.com",
    # Cloud Monitoring: metrics, dashboards, and alerting (see monitoring.tf).
    "monitoring.googleapis.com",
    # Cloud Build: Google's managed build service; enabled because the container
    # build/analysis pipeline relies on it.
    "cloudbuild.googleapis.com",
    # Container Analysis: stores and serves metadata (e.g. vulnerability scan
    # results) about container images.
    "containeranalysis.googleapis.com",
    # Binary Authorization: a deploy-time gate that can require images to meet
    # policy (e.g. be signed / scanned) before Cloud Run will run them.
    "binaryauthorization.googleapis.com",
    # NOTE: Container Scanning (containerscanning.googleapis.com) is deliberately
    # NOT enabled. Image vulnerability scanning is done by Trivy in CI
    # (deploy.yml, publish-gcp job), which gates the push. We do not want GCP's
    # automatic Artifact Registry scanning turned on - leave it disabled.
    # Secret Manager: secure storage for secrets. Enabled for availability even
    # though the static site itself stores no secrets here.
    "secretmanager.googleapis.com",
  ]
}

# A `resource` block tells Terraform to CREATE and manage a real cloud object
# (as opposed to a `data` source, which only READS something that already
# exists). The first label "google_project_service" is the resource type - it
# comes from the Google provider configured in versions.tf, which is the plugin
# that translates these blocks into Google Cloud API calls. The second label
# "apis" is a local name we choose to refer to this resource elsewhere.
# This particular resource type enables a single API on a project.
resource "google_project_service" "apis" {
  # `for_each` creates one copy of this resource per element in a set/map -
  # here, one "enable this API" object for each entry in required_apis. (Using
  # for_each instead of a single block keeps each API tracked individually in
  # state, so adding/removing one API only touches that one.) `toset(...)`
  # converts the list into a set, which is the type for_each expects; it also
  # makes each API name its own stable key. `local.required_apis` references
  # the local value defined above.
  for_each = toset(local.required_apis)
  # Which GCP project to enable the API in. `var.project_id` reads the input
  # variable defined in variables.tf (default "csoh-org-495800"). Referencing a
  # variable like this avoids hard-coding the project ID in many places.
  project = var.project_id
  # The API to enable for this instance of the loop. Inside a for_each block,
  # `each.value` is the current element - here the API name string (and because
  # we used toset, `each.key` is the same string).
  service = each.value
  # By default, removing this resource (or `terraform destroy`) would DISABLE
  # the API. Setting this to false leaves the API enabled on destroy, so we
  # don't accidentally break other resources or projects still relying on it.
  disable_on_destroy = false
}
