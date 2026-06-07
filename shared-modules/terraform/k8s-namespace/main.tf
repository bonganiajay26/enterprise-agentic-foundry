# Shared Terraform Module: Kubernetes Namespace
# Creates a namespace with: ResourceQuota, LimitRange, NetworkPolicy (default-deny),
# ServiceAccount, and RBAC bindings.
# Usage: module "prod_namespace" { source = "../../shared-modules/terraform/k8s-namespace" }

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
  }
}

resource "kubernetes_namespace" "this" {
  metadata {
    name = var.namespace_name
    labels = merge(
      {
        "name"                          = var.namespace_name
        "environment"                   = var.environment
        "managed-by"                    = "terraform"
        "pod-security.kubernetes.io/enforce" = var.pod_security_standard
        "pod-security.kubernetes.io/warn"    = "restricted"
      },
      var.additional_labels,
    )
    annotations = var.additional_annotations
  }
}

resource "kubernetes_resource_quota" "this" {
  metadata {
    name      = "${var.namespace_name}-quota"
    namespace = kubernetes_namespace.this.metadata[0].name
  }
  spec {
    hard = {
      "requests.cpu"    = var.quota_cpu_requests
      "requests.memory" = var.quota_memory_requests
      "limits.cpu"      = var.quota_cpu_limits
      "limits.memory"   = var.quota_memory_limits
      "pods"            = tostring(var.quota_max_pods)
      "persistentvolumeclaims" = tostring(var.quota_max_pvcs)
      "services"        = tostring(var.quota_max_services)
      "secrets"         = tostring(var.quota_max_secrets)
      "configmaps"      = tostring(var.quota_max_configmaps)
    }
  }
}

resource "kubernetes_limit_range" "this" {
  metadata {
    name      = "${var.namespace_name}-limitrange"
    namespace = kubernetes_namespace.this.metadata[0].name
  }
  spec {
    limit {
      type = "Container"
      default = {
        cpu    = var.default_cpu_limit
        memory = var.default_memory_limit
      }
      default_request = {
        cpu    = var.default_cpu_request
        memory = var.default_memory_request
      }
      max = {
        cpu    = var.max_cpu_per_container
        memory = var.max_memory_per_container
      }
    }
    limit {
      type = "PersistentVolumeClaim"
      max = {
        storage = var.max_pvc_size
      }
    }
  }
}

resource "kubernetes_network_policy" "default_deny" {
  metadata {
    name      = "default-deny-all"
    namespace = kubernetes_namespace.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}

resource "kubernetes_network_policy" "allow_dns" {
  metadata {
    name      = "allow-dns-egress"
    namespace = kubernetes_namespace.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      ports {
        port     = "53"
        protocol = "UDP"
      }
      ports {
        port     = "53"
        protocol = "TCP"
      }
    }
  }
}

resource "kubernetes_network_policy" "allow_same_namespace" {
  metadata {
    name      = "allow-same-namespace"
    namespace = kubernetes_namespace.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
    ingress {
      from {
        pod_selector {}
      }
    }
    egress {
      to {
        pod_selector {}
      }
    }
  }
}
