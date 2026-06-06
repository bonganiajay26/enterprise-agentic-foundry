variable "prefix" {
  description = "Naming prefix for all resources"
  type        = string
  default     = "platform"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "location" {
  description = "Primary Azure region"
  type        = string
  default     = "eastus2"
}

variable "dr_location" {
  description = "DR Azure region for geo-replication"
  type        = string
  default     = "westus2"
}

variable "vnet_address_space" {
  description = "VNet address space"
  type        = string
  default     = "10.0.0.0/16"
}

variable "aks_nodes_subnet_cidr" {
  type    = string
  default = "10.0.1.0/24"
}

variable "aks_pods_subnet_cidr" {
  type    = string
  default = "10.0.64.0/18"
}

variable "private_endpoints_subnet_cidr" {
  type    = string
  default = "10.0.2.0/26"
}

variable "kubernetes_version" {
  description = "AKS Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "system_node_pool_count" {
  type    = number
  default = 3
}

variable "system_node_pool_vm_size" {
  type    = string
  default = "Standard_D2s_v5"
}

variable "system_node_pool_max_count" {
  type    = number
  default = 5
}

variable "workload_node_pool_vm_size" {
  type    = string
  default = "Standard_D4s_v5"
}

variable "workload_node_pool_min_count" {
  type    = number
  default = 2
}

variable "workload_node_pool_max_count" {
  type    = number
  default = 20
}

variable "aks_admin_group_ids" {
  description = "Azure AD group IDs for AKS cluster admins"
  type        = list(string)
  default     = []
}

variable "allowed_ip_ranges" {
  description = "Allowed IP ranges for ACR and Key Vault"
  type        = list(string)
  default     = []
}

variable "owner" {
  type    = string
  default = "platform-team"
}

variable "cost_center" {
  type    = string
  default = "engineering"
}
