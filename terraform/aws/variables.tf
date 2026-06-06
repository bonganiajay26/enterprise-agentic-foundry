variable "prefix" {
  description = "Naming prefix for all resources"
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
  description = "AWS primary region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "intra_subnet_cidrs" {
  type    = list(string)
  default = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]
}

variable "kubernetes_version" {
  type    = string
  default = "1.28"
}

variable "system_node_type" {
  type    = string
  default = "t3.medium"
}

variable "workload_node_types" {
  type    = list(string)
  default = ["m5.large", "m5.xlarge", "m5a.large"]
}

variable "workload_min_nodes" {
  type    = number
  default = 2
}

variable "workload_max_nodes" {
  type    = number
  default = 20
}

variable "workload_desired_nodes" {
  type    = number
  default = 3
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access EKS API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "access_entries" {
  description = "EKS access entries for IAM principals"
  type        = map(any)
  default     = {}
}

variable "owner" {
  type    = string
  default = "platform-team"
}

variable "cost_center" {
  type    = string
  default = "engineering"
}
