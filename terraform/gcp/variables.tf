variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "prefix" {
  description = "Naming prefix"
  type        = string
  default     = "platform"
}

variable "environment" {
  description = "Environment (dev, staging, production)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Must be: dev, staging, or production."
  }
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-central1"
}

variable "nodes_cidr" {
  type    = string
  default = "10.0.0.0/24"
}

variable "pods_cidr" {
  type    = string
  default = "10.64.0.0/14"
}

variable "services_cidr" {
  type    = string
  default = "10.0.16.0/20"
}

variable "kubernetes_version" {
  description = "Minimum GKE version (use release channel instead when possible)"
  type        = string
  default     = "1.28"
}

variable "system_machine_type" {
  type    = string
  default = "e2-medium"
}

variable "workload_machine_type" {
  type    = string
  default = "e2-standard-4"
}

variable "workload_min_nodes" {
  type    = number
  default = 2
}

variable "workload_max_nodes" {
  type    = number
  default = 20
}

variable "authorized_networks" {
  description = "Authorized networks for GKE master access"
  type = list(object({
    cidr = string
    name = string
  }))
  default = [{ cidr = "0.0.0.0/0", name = "all" }]
}
