# Keyless deploy from GitHub Actions — the Azure counterpart to GCP WIF and
# the AWS OIDC role. An Entra ID app registration trusts GitHub's OIDC issuer
# via a federated credential; the workflow's token is exchanged for an Azure
# access token. No client secret is ever created or stored.
data "azuread_client_config" "current" {}

resource "azuread_application" "github" {
  display_name = "csoh-site-github-publisher"
  owners       = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "github" {
  client_id = azuread_application.github.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

# The federated credential locks the trust to this repo's `production` GitHub
# Environment. The deploy jobs declare `environment: production`, so the OIDC
# sub claim is `repo:OWNER/REPO:environment:production` (not the
# `ref:refs/heads/...` form) — `subject` must match that. The branch
# restriction is enforced by the GitHub Environment itself (main-only).
resource "azuread_application_federated_identity_credential" "github" {
  application_id = azuread_application.github.id
  display_name   = "github-production"
  description    = "GitHub Actions OIDC (production environment) for ${var.github_owner}/${var.github_repo}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_owner}/${var.github_repo}:environment:production"
}

# Least privilege: the publisher can read/write blob data in THIS storage
# account only. "Storage Blob Data Contributor" is the data-plane role needed
# to upload into $web; it grants no control-plane (account management) rights.
resource "azurerm_role_assignment" "github_blob_writer" {
  scope                = azurerm_storage_account.site.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.github.object_id
}
