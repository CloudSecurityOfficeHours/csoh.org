output "load_balancer_ip" {
  description = "Anycast IP for Cloudflare A record(s)"
  value       = google_compute_global_address.site.address
}

output "cloud_run_service_url" {
  description = "Direct Cloud Run URL (bypasses LB; for debugging only)"
  value       = google_cloud_run_v2_service.site.uri
}

output "artifact_registry_repo" {
  description = "Repo path for docker push"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "wif_provider" {
  description = "Full WIF provider resource name (for GitHub Actions auth step)"
  value       = "projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/providers/${google_iam_workload_identity_pool_provider.github.workload_identity_pool_provider_id}"
}

output "deployer_sa_email" {
  description = "Service account GitHub Actions impersonates"
  value       = google_service_account.deployer.email
}
