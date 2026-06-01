# An `output` is a value Terraform prints after `terraform apply` and saves in
# its state file so other tools can read it. Think of outputs as the "return
# values" of this Terraform module: they surface a few useful facts about the
# real Azure objects we just created (hostnames, names, IDs) so humans and
# automation don't have to dig through the Azure Portal to find them. Each
# `output "NAME" { ... }` block has a `description` (a human note) and a `value`
# (what to publish). The values below read attributes off resources defined in
# the sibling files (storage.tf, identity.tf) using the form
# `TYPE.NAME.attribute` - for example `azurerm_storage_account.site.name` means
# "the `name` attribute of the storage account resource named `site`". The
# GitHub Actions deploy workflow reads these outputs so it knows which storage
# account to upload to and which identity to log in as, with no value hardcoded
# in two places.
#
# The hostname of the Azure static-website endpoint, e.g.
# "csohorgsite.z13.web.core.windows.net" (no "https://" prefix - that is why the
# description says to strip the scheme). Cloudflare's load balancer treats this
# hostname as the "Azure origin": one of the three backends it forwards visitor
# traffic to when it routes a request to the Azure cloud. `primary_web_host` is
# the bare host; the `..._endpoint` output below is the same thing with the full
# "https://" URL.
output "static_website_host" {
  description = "Azure $web static-website hostname - the Cloudflare LB origin for Azure (strip the https:// scheme from the endpoint)."
  value       = azurerm_storage_account.site.primary_web_host
}

# Same static-website address as above, but the full HTTPS URL (e.g.
# "https://csohorgsite.z13.web.core.windows.net/"). Handy for opening the Azure
# origin directly in a browser or curl to confirm it serves the site before
# Cloudflare is pointed at it. Azure issues and renews the TLS certificate for
# this endpoint automatically, so it is HTTPS out of the box.
output "static_website_endpoint" {
  description = "Full HTTPS endpoint for the static website."
  value       = azurerm_storage_account.site.primary_web_endpoint
}

# The name of the storage account that holds the site's files (defined in
# storage.tf, e.g. "csohorgsite"). During a deploy, CI runs
# `az storage blob upload-batch` to copy the freshly built site into the
# account's special `$web` container; that command needs the exact account name
# to target. Publishing it here keeps the workflow and Terraform agreed on which
# account is the Azure origin.
output "storage_account_name" {
  description = "Storage account name for `az storage blob upload-batch` in CI."
  value       = azurerm_storage_account.site.name
}

# The client ID of the Entra ID (Azure Active Directory) application that
# GitHub Actions logs in as, defined in identity.tf. Remember deploys are
# keyless: instead of a stored password, the workflow presents a short-lived
# OIDC token from GitHub and Azure trusts it (this is "OIDC federation"). To
# start that login, the `azure/login` step must be told which app to
# authenticate as - that identifier is this client ID, which the workflow reads
# into its AZURE_CLIENT_ID input. A client ID is a public identifier, not a
# secret (it grants nothing by itself - only the approved GitHub workflow can
# complete the federated login), so this output is plain text and is
# deliberately not marked `sensitive`.
output "github_client_id" {
  description = "Entra app client ID for the azure/login OIDC step (AZURE_CLIENT_ID)."
  value       = azuread_application.github.client_id
}

# The tenant ID is the unique identifier of the Entra ID directory (the Azure
# "tenant" - your organization's whole identity boundary) that the app above
# lives in. The `azure/login` step needs it alongside the client ID to know
# WHICH directory to authenticate against, and reads it into its AZURE_TENANT_ID
# input. Rather than referencing a resource we created, this value comes from a
# `data` source - `data.azuread_client_config.current` (see identity.tf) reads
# back facts about whoever is currently running Terraform, and `.tenant_id` is
# the tenant they are signed into. A tenant ID is not a secret either, so it is
# published as plain text.
output "tenant_id" {
  description = "Entra tenant ID (AZURE_TENANT_ID) for the azure/login OIDC step."
  value       = data.azuread_client_config.current.tenant_id
}
