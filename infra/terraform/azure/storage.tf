resource "azurerm_resource_group" "site" {
  name     = var.resource_group_name
  location = var.location
}

# StorageV2 account. TLS 1.2 floor and HTTPS-only traffic so the Cloudflare
# origin leg can run at Full (strict). Static website serves anonymous reads
# from the special $web container only — no other blob is public.
resource "azurerm_storage_account" "site" {
  name                            = var.storage_account_name
  resource_group_name             = azurerm_resource_group.site.name
  location                        = azurerm_resource_group.site.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = true # required for the $web static site

  tags = {
    project   = "csoh.org"
    managedBy = "terraform"
    component = "static-origin"
  }
}

# Enable the static website. Azure serves $web over a built-in HTTPS endpoint
# (https://<account>.zNN.web.core.windows.net) with a managed cert — no LB or
# CDN required. Azure static websites support a 404 document but have no 403
# concept (there are no forbidden objects in $web), which is fine: we never
# upload sensitive files (see tools/site-publish.filter).
resource "azurerm_storage_account_static_website" "site" {
  storage_account_id = azurerm_storage_account.site.id
  index_document     = "index.html"
  error_404_document = "404.html"
}
