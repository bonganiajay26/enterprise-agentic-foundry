variable "namespace_name" {
  description = "Kubernetes namespace name"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.namespace_name))
    error_message = "Namespace name must be lowercase alphanumeric with hyphens"
  }
}

variable "environment" {
  type    = string
  default = "production"
}

variable "pod_security_standard" {
  description = "Pod Security Standards enforcement level"
  type        = string
  default     = "restricted"
  validation {
    condition     = contains(["privileged", "baseline", "restricted"], var.pod_security_standard)
    error_message = "Must be: privileged, baseline, or restricted"
  }
}

variable "quota_cpu_requests" {
  type    = string
  default = "4"
}

variable "quota_memory_requests" {
  type    = string
  default = "8Gi"
}

variable "quota_cpu_limits" {
  type    = string
  default = "8"
}

variable "quota_memory_limits" {
  type    = string
  default = "16Gi"
}

variable "quota_max_pods" {
  type    = number
  default = 50
}

variable "quota_max_pvcs" {
  type    = number
  default = 10
}

variable "quota_max_services" {
  type    = number
  default = 20
}

variable "quota_max_secrets" {
  type    = number
  default = 50
}

variable "quota_max_configmaps" {
  type    = number
  default = 50
}

variable "default_cpu_request" {
  type    = string
  default = "100m"
}

variable "default_memory_request" {
  type    = string
  default = "128Mi"
}

variable "default_cpu_limit" {
  type    = string
  default = "500m"
}

variable "default_memory_limit" {
  type    = string
  default = "512Mi"
}

variable "max_cpu_per_container" {
  type    = string
  default = "4"
}

variable "max_memory_per_container" {
  type    = string
  default = "8Gi"
}

variable "max_pvc_size" {
  type    = string
  default = "100Gi"
}

variable "additional_labels" {
  type    = map(string)
  default = {}
}

variable "additional_annotations" {
  type    = map(string)
  default = {}
}
