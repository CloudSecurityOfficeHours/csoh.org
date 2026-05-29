# Azure origin for csoh.org — a Storage Account "static website" ($web
# container) served over its built-in HTTPS endpoint, fronted by Cloudflare.
#
# State shares the GCP GCS bucket under a separate prefix (see the AWS dir
# for the rationale: one secured state store, pennies of storage).
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }

  backend "gcs" {
    bucket = "csoh-org-495800-tfstate"
    prefix = "csoh/azure"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

provider "azuread" {
  tenant_id = var.tenant_id
}
