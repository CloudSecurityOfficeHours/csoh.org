# This file declares the INPUT VARIABLES for the Azure part of the site's
# infrastructure. A Terraform "variable" is a named knob you can set from the
# outside (a CLI flag, an environment variable, or a .tfvars file) without
# editing the code. Elsewhere in this folder the variables are read with the
# syntax `var.<name>` - for example `var.location`. Each block below can set:
#   - description: human-readable note explaining the knob (shown in tooling)
#   - type:        the kind of value allowed; `string` here means plain text
#   - default:     the value used when nobody passes one in, so `terraform
#                  apply` works with no extra arguments. A variable with a
#                  default is effectively optional.
# None of these are marked `sensitive`, because IDs/names below are not secrets
# (the real secret - a cloud password or key - is deliberately never used here;
# GitHub Actions authenticates with short-lived OIDC tokens instead).
# ---------------------------------------------------------------------------
# Azure organizes everything you pay for inside a "subscription" (a billing +
# isolation boundary, identified by this GUID). This variable pins which one
# the deploy targets. It is wired into the azurerm provider in versions.tf
# (`subscription_id = var.subscription_id`). Pinning it matters because the
# `az` CLI a person is logged into may default to some OTHER subscription;
# hardcoding it here guarantees the site's resources always land in the right
# place instead of wherever the current login happens to point.
variable "subscription_id" {
  description = "Azure subscription this stack must deploy into. Pinned on the azurerm provider so the deploy can't silently land in whatever subscription the active az login happens to point at."
  type        = string
  default     = "f973ebad-a06c-4d5c-8161-0faf2a13076c"
}

# A "tenant" is your organization's identity directory in Microsoft Entra ID
# (the service formerly called Azure Active Directory) - it's where users, app
# registrations, and login/permission rules live. Every subscription belongs to
# one tenant. This GUID identifies ours and is pinned on BOTH providers in
# versions.tf: the azurerm provider (which manages resources) and the azuread
# provider (which manages identity objects like the GitHub OIDC app). It must
# match the subscription above, since the OIDC trust that lets GitHub deploy is
# created inside this tenant (see identity.tf).
variable "tenant_id" {
  description = "Azure AD (Entra) tenant for the subscription + OIDC app registration. Pinned on both the azurerm and azuread providers."
  type        = string
  default     = "10e6d2fb-a320-46fa-8df1-9aa7a8f6b2dc"
}

# An Azure "region" (here called location) is the physical datacenter group
# where your resources run, e.g. "eastus" = US East. It's used in storage.tf
# for both the resource group and the storage account. The exact region matters
# less than usual for this project: the static site is cached and served
# globally by Cloudflare's edge, so this Azure copy is just one of three origins
# Cloudflare falls back to - visitors rarely hit it directly.
variable "location" {
  description = "Azure region for the resource group + storage account."
  type        = string
  default     = "eastus"
}

# A "resource group" is an Azure container that holds related resources so they
# can be managed and deleted together - think of it as a labeled folder for this
# project's Azure objects. storage.tf creates a group with this name and then
# places the storage account inside it. Deleting the group would delete
# everything in it, so the name is fixed here to keep deploys pointed at the
# same folder every time.
variable "resource_group_name" {
  description = "Resource group holding the site's Azure resources."
  type        = string
  default     = "csoh-site"
}

# A "storage account" is Azure's object-storage service (the rough equivalent
# of an AWS S3 bucket or a GCS bucket). It holds the site's files. Azure turns
# such an account into a website by serving a special container named "$web"
# over a built-in HTTPS address - that address is the Azure ORIGIN that
# Cloudflare's load balancer sends traffic to. The name has strict rules
# because it becomes part of a public hostname: it must be GLOBALLY unique
# across all of Azure (no other customer can have taken it) and 3-24 lowercase
# letters/digits only - hence "csohorgsite" with no dots or dashes. Used in
# storage.tf as the account's `name`.
variable "storage_account_name" {
  description = "Globally-unique storage account name (3-24 chars, lowercase alphanumeric). Its $web static-website endpoint is the Cloudflare LB origin for Azure."
  type        = string
  default     = "csohorgsite"
}

# The next three variables identify the exact GitHub repository (and branch)
# that is allowed to deploy this site, and together they "scope" the OIDC trust.
# Background: instead of storing a long-lived Azure password/key in GitHub
# (which could leak), the deploy uses OIDC FEDERATION. When a GitHub Actions job
# runs, GitHub hands it a short-lived, signed identity token describing WHO is
# running and WHERE (which owner, repo, branch, environment). Azure is
# configured (in identity.tf) to trust that token, but only if its details
# match values it was told to expect. These variables supply those expected
# values, so the trust is narrow: only this owner's repo can obtain Azure
# credentials, and only briefly. This is "least privilege" - grant the minimum
# access to the minimum identity.
# This first variable, github_owner, is the GitHub organization (or user)
# account that owns the repo. It's combined with github_repo in identity.tf to
# build the token's expected "subject" string, e.g.
# repo:OWNER/REPO:environment:production.
variable "github_owner" {
  description = "GitHub org/user that owns the repo (scopes the OIDC trust)."
  type        = string
  default     = "CloudSecurityOfficeHours"
}

# The repository name (the part after the owner, e.g. the "csoh.org" in
# CloudSecurityOfficeHours/csoh.org). Paired with github_owner in identity.tf
# to pin the OIDC trust to this one repo and no other.
variable "github_repo" {
  description = "GitHub repo name (scopes the OIDC trust)."
  type        = string
  default     = "csoh.org"
}

# The branch that is allowed to publish - "main", the line of code that goes
# live. Note a subtlety: this stack's OIDC trust is keyed to a GitHub
# "Environment" named production (subject ...:environment:production in
# identity.tf), NOT directly to a branch name. The main-only rule is actually
# enforced by that GitHub Environment's own protection settings. So this
# variable documents the intended branch and is available for reference, but it
# is not interpolated into the trust subject the way the owner/repo are.
variable "github_branch" {
  description = "Branch authorized to publish via OIDC."
  type        = string
  default     = "main"
}
