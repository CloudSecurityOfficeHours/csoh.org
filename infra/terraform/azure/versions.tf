# Azure origin for csoh.org - a Storage Account "static website" ($web
# container) served over its built-in HTTPS endpoint, fronted by Cloudflare.
#
# State shares the GCP GCS bucket under a separate prefix (see the AWS dir
# for the rationale: one secured state store, pennies of storage).
# The "terraform" block configures Terraform itself (not any cloud). It is
# settings ABOUT this project: which Terraform version is allowed to run it,
# which provider plugins to download, and where to keep the state file. There
# is exactly one of these per directory, and it creates no cloud resources.
terraform {
  # Refuse to run unless the installed Terraform CLI is at least version 1.6.0.
  # ">=" means "this version or newer". This guards against someone using an
  # old CLI that lacks features/syntax this code relies on.
  required_version = ">= 1.6.0"

  # A "provider" is a plugin that teaches Terraform how to talk to one specific
  # API (here, Azure). Terraform core knows nothing about clouds on its own; it
  # downloads these plugins to actually create/read/update/delete resources.
  # This block lists every provider this directory uses, where to fetch it
  # ("source", a name in the public Terraform Registry), and which versions are
  # acceptable ("version"). Pinning versions keeps runs reproducible so a new
  # plugin release can't silently change behavior.
  required_providers {
    # azurerm = the Azure Resource Manager provider. It manages the actual
    # infrastructure: the resource group, the storage account, the static
    # website, role assignments (see storage.tf and identity.tf).
    azurerm = {
      # "source" is the registry address; "hashicorp/azurerm" is shorthand for
      # registry.terraform.io/hashicorp/azurerm (HashiCorp is Terraform's maker).
      source = "hashicorp/azurerm"
      # "~> 4.0" is a pessimistic constraint: allow any 4.x version (4.0, 4.1,
      # 4.99 ...) but NOT 5.0. This accepts safe patch/minor updates while
      # blocking a major version that could introduce breaking changes.
      version = "~> 4.0"
    }
    # azuread = the Azure Active Directory / Entra ID provider. It manages
    # identity objects (the app registration, service principal, and the
    # GitHub OIDC federated credential in identity.tf) - the "who can deploy"
    # half, separate from the "what gets deployed" half above.
    azuread = {
      source = "hashicorp/azuread"
      # Allow any 3.x of the azuread provider, but not 4.0.
      version = "~> 3.0"
    }
  }

  # Terraform records everything it has created in a "state file" - a JSON map
  # between this code and the real cloud objects. By default that file lives on
  # your laptop, which is fragile and unshareable. A "backend" stores it
  # remotely instead, so CI and every teammate read/write the SAME state and
  # don't clobber each other. This project reuses ONE Google Cloud Storage
  # (GCS) bucket for all three clouds' state, isolating each under its own
  # "prefix" (folder). Note: the backend that HOLDS the state (GCS) is
  # independent of the clouds this code MANAGES (Azure) - they need not match.
  backend "gcs" {
    # The GCS bucket that holds the shared state files (created in the GCP dir).
    bucket = "csoh-org-495800-tfstate"
    # Folder within that bucket for THIS stack's state, keeping Azure's state
    # separate from the aws/ and gcp/ stacks that share the same bucket.
    prefix = "csoh/azure"
  }
}

# Having LISTED the providers above, this block CONFIGURES the azurerm one:
# how it connects to Azure. It does NOT create anything. Credentials are NOT
# set here - in CI the github actions azure/login step supplies short-lived
# OIDC tokens (no stored secret), and locally Terraform uses your `az login`
# session. We only pin WHICH subscription and tenant to act in.
provider "azurerm" {
  # azurerm requires this block even when empty; it can toggle provider-wide
  # behaviors (e.g. whether deleting a resource group force-deletes contents).
  # Empty "{}" means "use all the safe defaults".
  features {}
  # Pin the target subscription (an Azure billing/isolation boundary, like an
  # AWS account). "var.subscription_id" reads the value from variables.tf.
  # Pinning it prevents the deploy from landing in whatever subscription your
  # local `az` session happens to point at.
  subscription_id = var.subscription_id
  # Pin the Entra ID (Azure AD) tenant - the directory of users/apps that owns
  # this subscription. Set on BOTH providers so they operate in the same tenant.
  tenant_id = var.tenant_id
}

# Configure the azuread provider used for the identity objects in identity.tf.
# It only needs to know which tenant (directory) to manage; like azurerm above,
# it gets its credentials from the ambient OIDC/`az login` session.
provider "azuread" {
  # Same tenant value as azurerm, sourced from the shared input variable.
  tenant_id = var.tenant_id
}
