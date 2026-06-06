# GCP Landing Zone — GKE Platform
# Terraform >= 1.6 required

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.10"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.10"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
  }
  backend "gcs" {
    bucket = "your-tfstate-bucket"
    prefix = "gcp-platform/terraform.tfstate"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

data "google_client_config" "default" {}

# ─── Enable APIs ──────────────────────────────────────────────────────
resource "google_project_service" "required_apis" {
  for_each = toset([
    "container.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "cloudbuild.googleapis.com",
    "dns.googleapis.com",
    "servicenetworking.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ─── VPC ──────────────────────────────────────────────────────────────
resource "google_compute_network" "platform" {
  name                    = "${var.prefix}-${var.environment}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.required_apis]
}

resource "google_compute_subnetwork" "gke_nodes" {
  name                     = "${var.prefix}-${var.environment}-gke-subnet"
  ip_cidr_range            = var.nodes_cidr
  region                   = var.region
  network                  = google_compute_network.platform.id
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# ─── Artifact Registry ────────────────────────────────────────────────
resource "google_artifact_registry_repository" "platform" {
  location      = var.region
  repository_id = "${var.prefix}-${var.environment}"
  description   = "Platform container registry"
  format        = "DOCKER"

  docker_config {
    immutable_tags = true
  }

  cleanup_policies {
    id     = "keep-last-30"
    action = "KEEP"
    most_recent_versions {
      keep_count = 30
    }
  }

  depends_on = [google_project_service.required_apis]
}

# ─── Cloud KMS ────────────────────────────────────────────────────────
resource "google_kms_key_ring" "platform" {
  name       = "${var.prefix}-${var.environment}-keyring"
  location   = var.region
  depends_on = [google_project_service.required_apis]
}

resource "google_kms_crypto_key" "gke_secrets" {
  name            = "gke-secrets"
  key_ring        = google_kms_key_ring.platform.id
  rotation_period = "7776000s"  # 90 days

  lifecycle {
    prevent_destroy = true
  }
}

# ─── GKE Cluster ──────────────────────────────────────────────────────
resource "google_container_cluster" "platform" {
  provider = google-beta
  name     = "${var.prefix}-${var.environment}-gke"
  location = var.region

  network    = google_compute_network.platform.name
  subnetwork = google_compute_subnetwork.gke_nodes.name

  # Remove default node pool, use managed node pools
  remove_default_node_pool = true
  initial_node_count       = 1

  # Networking
  networking_mode = "VPC_NATIVE"
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Private cluster
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.authorized_networks
      content {
        cidr_block   = cidr_blocks.value.cidr
        display_name = cidr_blocks.value.name
      }
    }
  }

  # Security
  database_encryption {
    state    = "ENCRYPTED"
    key_name = google_kms_crypto_key.gke_secrets.id
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Addons
  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
    gcs_fuse_csi_driver_config {
      enabled = true
    }
  }

  # Logging & monitoring
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }
  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS", "DAEMONSET", "DEPLOYMENT", "HPA"]
    managed_prometheus {
      enabled = true
    }
  }

  # Binary Authorization
  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  }

  # Release channel
  release_channel {
    channel = "REGULAR"
  }

  # Maintenance policy
  maintenance_policy {
    recurring_window {
      start_time = "2024-01-01T02:00:00Z"
      end_time   = "2024-01-01T06:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SU"
    }
  }

  depends_on = [google_project_service.required_apis]
}

# ─── Node Pools ───────────────────────────────────────────────────────
resource "google_container_node_pool" "system" {
  name     = "system"
  cluster  = google_container_cluster.platform.name
  location = var.region

  autoscaling {
    min_node_count = 1
    max_node_count = 5
  }

  node_config {
    machine_type    = var.system_machine_type
    disk_size_gb    = 100
    disk_type       = "pd-ssd"
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.gke_nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      role = "system"
    }

    taint {
      key    = "CriticalAddonsOnly"
      value  = "true"
      effect = "NO_SCHEDULE"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0
  }
}

resource "google_container_node_pool" "workloads" {
  name     = "workloads"
  cluster  = google_container_cluster.platform.name
  location = var.region

  autoscaling {
    min_node_count = var.workload_min_nodes
    max_node_count = var.workload_max_nodes
  }

  node_config {
    machine_type    = var.workload_machine_type
    disk_size_gb    = 128
    disk_type       = "pd-ssd"
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.gke_nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      role = "workload"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ─── Service Accounts ─────────────────────────────────────────────────
resource "google_service_account" "gke_nodes" {
  account_id   = "${var.prefix}-${var.environment}-gke-nodes"
  display_name = "GKE Node Service Account"
}

resource "google_project_iam_member" "gke_nodes_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_project_iam_member" "gke_nodes_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_project_iam_member" "gke_nodes_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}
