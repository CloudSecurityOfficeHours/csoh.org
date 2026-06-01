# A "resource" block tells Terraform to CREATE and manage a real cloud object
# (contrast with a "data" source, which only READS something that already
# exists - you'll see one of those in identity.tf). The two strings after
# "resource" are the type ("azurerm_resource_group") and a local name ("site")
# you use to refer back to this object elsewhere in the code.
#
# In Azure, a Resource Group is a folder/container that holds related
# resources (here: the storage account below) so they share a lifecycle,
# region, and billing scope. Everything in this stack lives inside this group.
resource "azurerm_resource_group" "site" {
  # "var.NAME" reads an input variable (declared in variables.tf). This keeps
  # values configurable instead of hard-coded. Default here: "csoh-site".
  name = var.resource_group_name
  # The Azure region (e.g. "eastus") the group is created in. The storage
  # account below inherits this same location.
  location = var.location
}

# A Storage Account is Azure's container for blobs (files), and it's where
# this site's HTML/CSS/JS actually lives - this is the Azure "origin" that
# Cloudflare pulls from. The block below creates a StorageV2 account with a
# TLS 1.2 floor and HTTPS-only traffic (so the Cloudflare origin leg can run at
# Full (strict)), serving anonymous reads from the special $web container only.
# (Note: AWS uses an S3 bucket + CloudFront for the same job; GCP uses nginx on
# Cloud Run. All three clouds serve the identical site bytes behind one
# Cloudflare edge.)
resource "azurerm_storage_account" "site" {
  # Globally-unique account name (3-24 lowercase alphanumeric chars). It
  # becomes part of the public hostname, so it must be unique across all of
  # Azure. Default: "csohorgsite".
  name = var.storage_account_name
  # Place this account inside the resource group created above. Writing
  # "azurerm_resource_group.site.name" REFERENCES that other resource's "name"
  # attribute - Terraform reads this as a dependency and will create the group
  # FIRST, then the account. No explicit depends_on is needed; the reference
  # itself wires up the ordering.
  resource_group_name = azurerm_resource_group.site.name
  # Reuse the group's region so the account lands in the same place.
  location = azurerm_resource_group.site.location
  # "Standard" = ordinary disk-backed storage (vs the pricier "Premium" SSD
  # tier). Plenty for serving a static site.
  account_tier = "Standard"
  # Replication strategy. LRS = Locally Redundant Storage: 3 copies kept within
  # one datacenter. Cheapest option; fine here because the real redundancy
  # comes from running three separate clouds behind Cloudflare, not from Azure
  # alone.
  account_replication_type = "LRS"
  # "StorageV2" is the modern general-purpose account kind and the one that
  # supports the static-website feature enabled further down.
  account_kind = "StorageV2"
  # Refuse any client negotiating older/weaker TLS than 1.2. This lets
  # Cloudflare connect to the origin over a properly secured link (its
  # "Full (strict)" mode).
  min_tls_version = "TLS1_2"
  # Reject plain HTTP entirely; only encrypted HTTPS requests are served.
  https_traffic_only_enabled = true
  # Static-website hosting works by serving anonymous (unauthenticated) reads
  # from the special "$web" container. That requires public access to be
  # permitted at the account level, which this flag does. Only $web is exposed
  # this way; no other blob is made public, and CI never uploads sensitive
  # files (see tools/site-publish.filter).
  allow_nested_items_to_be_public = true # required for the $web static site

  # Tags are free-form key/value labels attached to the resource. They don't
  # change behavior - they're for humans and tooling (cost reports, "who owns
  # this?", "what created it?"). The whole stack uses the same set.
  tags = {
    project   = "csoh.org"
    managedBy = "terraform"
    component = "static-origin"
  }
}

# This second resource flips on the "static website" feature for the account
# above. It's a separate block (rather than an argument inside the account)
# because Azure treats it as its own configuration object. Azure then serves
# $web over a built-in HTTPS endpoint (https://<account>.zNN.web.core.windows.net)
# with a managed cert - no LB or CDN required. Azure static websites support a
# 404 document but have no 403 concept (there are no forbidden objects in $web),
# which is fine: we never upload sensitive files (see tools/site-publish.filter).
resource "azurerm_storage_account_static_website" "site" {
  # Bind this setting to the storage account created above by referencing its
  # ".id" (the account's unique Azure resource identifier). This both targets
  # the right account and makes Terraform create the account before this.
  storage_account_id = azurerm_storage_account.site.id
  # The default file served at "/" (the homepage).
  index_document = "index.html"
  # The page returned for not-found URLs (HTTP 404).
  error_404_document = "404.html"
}
