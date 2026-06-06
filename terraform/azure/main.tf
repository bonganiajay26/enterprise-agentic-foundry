# Azure Landing Zone — AKS Platform
# Terraform >= 1.6 required

terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.85"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.47"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
  backend "azurerm" {
    resource_group_name  = "tfstate-rg"
    storage_account_name = "tfstatestorage"
    container_name       = "tfstate"
    key                  = "azure-platform.tfstate"
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

# ─── Data Sources ─────────────────────────────────────────────────────
data "azurerm_client_config" "current" {}
data "azurerm_subscription" "current" {}

# ─── Resource Group ───────────────────────────────────────────────────
resource "azurerm_resource_group" "platform" {
  name     = "${var.prefix}-${var.environment}-rg"
  location = var.location
  tags     = local.common_tags
}

# ─── Virtual Network ──────────────────────────────────────────────────
resource "azurerm_virtual_network" "platform" {
  name                = "${var.prefix}-${var.environment}-vnet"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  address_space       = [var.vnet_address_space]
  tags                = local.common_tags
}

resource "azurerm_subnet" "aks_nodes" {
  name                 = "aks-nodes-subnet"
  resource_group_name  = azurerm_resource_group.platform.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = [var.aks_nodes_subnet_cidr]
}

resource "azurerm_subnet" "aks_pods" {
  name                 = "aks-pods-subnet"
  resource_group_name  = azurerm_resource_group.platform.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = [var.aks_pods_subnet_cidr]

  delegation {
    name = "aks-delegation"
    service_delegation {
      name    = "Microsoft.ContainerService/managedClusters"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "private-endpoints-subnet"
  resource_group_name  = azurerm_resource_group.platform.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = [var.private_endpoints_subnet_cidr]
  private_endpoint_network_policies_enabled = false
}

# ─── Container Registry ───────────────────────────────────────────────
resource "azurerm_container_registry" "platform" {
  name                = "${var.prefix}${var.environment}acr"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  sku                 = "Premium"
  admin_enabled       = false

  network_rule_set {
    default_action = "Deny"
    ip_rule {
      action   = "Allow"
      ip_range = var.allowed_ip_ranges[0]
    }
  }

  georeplications {
    location                = var.dr_location
    zone_redundancy_enabled = true
    tags                    = local.common_tags
  }

  retention_policy {
    days    = 30
    enabled = true
  }

  trust_policy {
    enabled = true
  }

  zone_redundancy_enabled = true
  tags                    = local.common_tags
}

# ─── Key Vault ────────────────────────────────────────────────────────
resource "azurerm_key_vault" "platform" {
  name                          = "${var.prefix}-${var.environment}-kv"
  location                      = azurerm_resource_group.platform.location
  resource_group_name           = azurerm_resource_group.platform.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "premium"
  soft_delete_retention_days    = 90
  purge_protection_enabled      = true
  public_network_access_enabled = false

  network_acls {
    bypass         = "AzureServices"
    default_action = "Deny"
  }

  tags = local.common_tags
}

# ─── Log Analytics Workspace ──────────────────────────────────────────
resource "azurerm_log_analytics_workspace" "platform" {
  name                = "${var.prefix}-${var.environment}-law"
  location            = azurerm_resource_group.platform.location
  resource_group_name = azurerm_resource_group.platform.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
  tags                = local.common_tags
}

# ─── AKS Cluster ──────────────────────────────────────────────────────
resource "azurerm_kubernetes_cluster" "platform" {
  name                = "${var.prefix}-${var.environment}-aks"
  location            = azurerm_resource_group.platform.location
  resource_group_name = azurerm_resource_group.platform.name
  dns_prefix          = "${var.prefix}-${var.environment}"
  kubernetes_version  = var.kubernetes_version

  # System node pool
  default_node_pool {
    name                        = "system"
    node_count                  = var.system_node_pool_count
    vm_size                     = var.system_node_pool_vm_size
    vnet_subnet_id              = azurerm_subnet.aks_nodes.id
    pod_subnet_id               = azurerm_subnet.aks_pods.id
    enable_auto_scaling         = true
    min_count                   = 1
    max_count                   = var.system_node_pool_max_count
    only_critical_addons_enabled = true
    os_disk_type                = "Ephemeral"
    os_disk_size_gb             = 100
    zones                       = ["1", "2", "3"]
    upgrade_settings {
      max_surge = "33%"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  # Network
  network_profile {
    network_plugin    = "azure"
    network_policy    = "cilium"
    ebpf_data_plane   = "cilium"
    load_balancer_sku = "standard"
    outbound_type     = "userAssignedNATGateway"
  }

  # OMS Agent (Azure Monitor)
  oms_agent {
    log_analytics_workspace_id      = azurerm_log_analytics_workspace.platform.id
    msi_auth_for_monitoring_enabled = true
  }

  # Azure AD integration
  azure_active_directory_role_based_access_control {
    managed                = true
    azure_rbac_enabled     = true
    admin_group_object_ids = var.aks_admin_group_ids
  }

  # Key Vault Secrets Provider
  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  # Workload Identity
  workload_identity_enabled         = true
  oidc_issuer_enabled               = true

  # Security
  http_application_routing_enabled  = false
  run_command_enabled               = false
  local_account_disabled            = true
  image_cleaner_enabled             = true
  image_cleaner_interval_hours      = 48

  # Auto-upgrade
  automatic_channel_upgrade = "patch"
  node_os_channel_upgrade   = "SecurityPatch"

  maintenance_window_auto_upgrade {
    frequency   = "Weekly"
    interval    = 1
    duration    = 4
    day_of_week = "Sunday"
    utc_offset  = "+00:00"
    start_time  = "02:00"
  }

  # Storage
  storage_profile {
    blob_driver_enabled         = true
    disk_driver_enabled         = true
    file_driver_enabled         = true
    snapshot_controller_enabled = true
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      default_node_pool[0].node_count,
      kubernetes_version,
    ]
  }
}

# ─── AKS User Node Pool ───────────────────────────────────────────────
resource "azurerm_kubernetes_cluster_node_pool" "workloads" {
  name                  = "workloads"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.platform.id
  vm_size               = var.workload_node_pool_vm_size
  vnet_subnet_id        = azurerm_subnet.aks_nodes.id
  pod_subnet_id         = azurerm_subnet.aks_pods.id
  enable_auto_scaling   = true
  min_count             = var.workload_node_pool_min_count
  max_count             = var.workload_node_pool_max_count
  os_disk_type          = "Ephemeral"
  os_disk_size_gb       = 128
  zones                 = ["1", "2", "3"]
  node_labels = {
    "workload-type" = "application"
  }
  tags = local.common_tags
}

# ─── RBAC: AKS → ACR ──────────────────────────────────────────────────
resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = azurerm_kubernetes_cluster.platform.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.platform.id
  skip_service_principal_aad_check = true
}

# ─── Locals ───────────────────────────────────────────────────────────
locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.prefix
    Owner       = var.owner
    CostCenter  = var.cost_center
  }
}
