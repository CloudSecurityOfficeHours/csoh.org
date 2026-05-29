output "static_website_host" {
  description = "Azure $web static-website hostname — the Cloudflare LB origin for Azure (strip the https:// scheme from the endpoint)."
  value       = azurerm_storage_account.site.primary_web_host
}

output "static_website_endpoint" {
  description = "Full HTTPS endpoint for the static website."
  value       = azurerm_storage_account.site.primary_web_endpoint
}

output "storage_account_name" {
  description = "Storage account name for `az storage blob upload-batch` in CI."
  value       = azurerm_storage_account.site.name
}

output "github_client_id" {
  description = "Entra app client ID for the azure/login OIDC step (AZURE_CLIENT_ID)."
  value       = azuread_application.github.client_id
}

output "tenant_id" {
  description = "Entra tenant ID (AZURE_TENANT_ID) for the azure/login OIDC step."
  value       = data.azuread_client_config.current.tenant_id
}
