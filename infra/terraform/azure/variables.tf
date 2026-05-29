variable "subscription_id" {
  description = "Azure subscription this stack must deploy into. Pinned on the azurerm provider so the deploy can't silently land in whatever subscription the active az login happens to point at."
  type        = string
  default     = "f973ebad-a06c-4d5c-8161-0faf2a13076c"
}

variable "tenant_id" {
  description = "Azure AD (Entra) tenant for the subscription + OIDC app registration. Pinned on both the azurerm and azuread providers."
  type        = string
  default     = "10e6d2fb-a320-46fa-8df1-9aa7a8f6b2dc"
}

variable "location" {
  description = "Azure region for the resource group + storage account."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Resource group holding the site's Azure resources."
  type        = string
  default     = "csoh-site"
}

variable "storage_account_name" {
  description = "Globally-unique storage account name (3-24 chars, lowercase alphanumeric). Its $web static-website endpoint is the Cloudflare LB origin for Azure."
  type        = string
  default     = "csohorgsite"
}

variable "github_owner" {
  description = "GitHub org/user that owns the repo (scopes the OIDC trust)."
  type        = string
  default     = "CloudSecurityOfficeHours"
}

variable "github_repo" {
  description = "GitHub repo name (scopes the OIDC trust)."
  type        = string
  default     = "csoh.org"
}

variable "github_branch" {
  description = "Branch authorized to publish via OIDC."
  type        = string
  default     = "main"
}
