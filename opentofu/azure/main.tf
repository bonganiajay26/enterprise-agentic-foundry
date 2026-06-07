# OpenTofu Azure Platform — Identical to terraform/azure/main.tf
# OpenTofu is a drop-in open-source fork of Terraform (MPL-2.0 licensed)
# Usage: tofu init && tofu plan && tofu apply

terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.85"
    }
  }
  # OpenTofu native state encryption (unique to OpenTofu)
  encryption {
    key_provider "pbkdf2" "mykey" {
      passphrase = var.state_encryption_passphrase
    }
    method "aes_gcm" "newmethod" {
      keys = key_provider.pbkdf2.mykey
    }
    state {
      method = method.aes_gcm.newmethod
    }
  }
  backend "azurerm" {
    resource_group_name  = "tfstate-rg"
    storage_account_name = "tfstatestorage"
    container_name       = "tfstate"
    key                  = "opentofu-azure-platform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

# Reference the main Azure module
module "platform" {
  source = "../../terraform/azure"

  prefix      = var.prefix
  environment = var.environment
  location    = var.location
}

variable "prefix" { type = string; default = "platform" }
variable "environment" { type = string }
variable "location" { type = string; default = "eastus2" }
variable "state_encryption_passphrase" {
  type      = string
  sensitive = true
  default   = ""
}
