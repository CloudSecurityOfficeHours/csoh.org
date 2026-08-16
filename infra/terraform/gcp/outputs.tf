# An "output" is a value Terraform prints after `terraform apply` and saves
# in state. Outputs are how one piece of infrastructure hands useful facts
# (URLs, names, IDs) to humans or to other automation. Nothing here CREATES
# cloud resources - every value below just reads an attribute off a resource
# defined in a sibling .tf file in this same folder, or stitches together a
# string from those attributes and the input variables in variables.tf.
# These four outputs exist mainly to feed the GitHub Actions deploy workflow.

# The public HTTPS address Google assigned to the Cloud Run service (looks
# like https://csoh-site-xxxx.run.app). Cloudflare uses this hostname as the
# GCP "origin" it forwards requests to - one of the three clouds behind the
# edge. `.uri` is an attribute Cloud Run fills in AFTER the service is created,
# so Terraform can only know it post-apply (hence surfacing it as an output).
# The note about stripping "https://" is for whoever pastes this into the
# Cloudflare origin config, which wants a bare hostname, not a full URL.
output "cloud_run_service_url" {
  # `description` is free-text shown next to the value in `terraform output`;
  # it documents the output for the next human, like a label.
  description = "Cloud Run *.run.app URL - this is the Cloudflare LB origin for GCP (strip the https:// scheme)."
  # `value` is what gets printed. The dotted name is a cross-resource
  # REFERENCE: "<resource_type>.<local_name>.<attribute>". Here it points at
  # the google_cloud_run_v2_service named "site" (in cloud_run.tf) and reads
  # its `uri`. Writing this reference also tells Terraform "build that service
  # before evaluating this output," so dependency order is automatic.
  value = google_cloud_run_v2_service.site.uri
}

# The full path of the Docker image repository, in the exact form the
# `docker push` command (run by CI) needs. Artifact Registry is Google's
# private container/image store; this site is shipped to Cloud Run as a
# container, so the built image must be pushed here first.
output "artifact_registry_repo" {
  description = "Repo path for docker push"
  # This value is BUILT by string interpolation: anything inside "${...}" is
  # evaluated and spliced into the surrounding text. `var.region` and
  # `var.project_id` come from variables.tf; the last piece reads the
  # `repository_id` ("csoh-containers") off the repo resource in
  # artifact_registry.tf. The fixed text "-docker.pkg.dev/" is Google's
  # standard Artifact Registry hostname pattern, so the result looks like
  # "us-central1-docker.pkg.dev/csoh-org-495800/csoh-containers".
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

# The full resource name of the Workload Identity Federation (WIF) provider.
# WIF is how GitHub Actions logs into GCP with NO stored password or JSON key:
# GitHub hands GCP a short-lived OIDC token proving "I'm a workflow run from
# this repo," and GCP trades it for a temporary access token. The deploy
# workflow must pass this exact provider name to the google-github-actions
# auth step so GCP knows which trust configuration to check the token against.
output "wif_provider" {
  description = "Full WIF provider resource name (for GitHub Actions auth step)"
  # Another interpolated string assembling GCP's required canonical format.
  # `var.project_number` is the numeric project ID (variables.tf). The two
  # resource references pull the IDs of the pool ("github-pool") and the
  # provider ("github-provider") created in wif.tf. The literal path segments
  # ("locations/global/workloadIdentityPools/.../providers/...") are the fixed
  # shape Google requires for this name - order and wording must match exactly.
  value = "projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/providers/${google_iam_workload_identity_pool_provider.github.workload_identity_pool_provider_id}"
}

# The email-style identifier of the "deployer" service account. A service
# account is a non-human identity that automation acts as. After WIF (above)
# authenticates the GitHub workflow, the workflow IMPERSONATES this account to
# actually do work - and this account is deliberately limited to just pushing
# images and deploying Cloud Run revisions (see service_accounts.tf), nothing
# more. That narrow grant is the "least privilege" principle: give an identity
# only the permissions it truly needs, so a leak can't do broad damage. The
# deploy workflow needs this email to name which account to impersonate.
output "deployer_sa_email" {
  description = "Service account GitHub Actions impersonates"
  # Reads the auto-generated `.email` attribute off the google_service_account
  # named "deployer" in service_accounts.tf (e.g.
  # csoh-deployer@csoh-org-495800.iam.gserviceaccount.com).
  value = google_service_account.deployer.email
}

# The QA service's *.run.app URL. Unlike the production one above, this is NOT
# fed to a Cloudflare load balancer pool - QA is deliberately kept out of the
# pool so it is never health-checked (see the cost note in cloud_run.tf). It is
# consumed instead by the origin rule in
# infra/terraform/cloudflare/rules.tf, which rewrites the Host header on
# requests to qa.csoh.org so Cloud Run can tell which service they are for.
# Strip the "https://" scheme when pasting it into that variable, same as the
# production origin hosts.
output "cloud_run_qa_service_url" {
  description = "Cloud Run *.run.app URL for the QA service (strip the https:// scheme to use as TF_VAR_gcp_qa_origin_host)."
  value       = google_cloud_run_v2_service.site_qa.uri
}

# The QA deploy identity, for the `service_account:` input of the
# google-github-actions/auth step in deploy-qa.yml. Deliberately a different
# account from `deployer_sa_email` above: its roles stop at the QA Cloud Run
# service, so this workflow cannot deploy production (see service_accounts.tf).
output "deployer_qa_sa_email" {
  description = "Service account deploy-qa.yml impersonates"
  value       = google_service_account.deployer_qa.email
}
