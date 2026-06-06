# AWS Landing Zone — EKS Platform
# Terraform >= 1.6 required

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
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
  backend "s3" {
    bucket         = "your-tfstate-bucket"
    key            = "aws-platform/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = local.common_tags
  }
}

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {}

# ─── VPC ──────────────────────────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.4"

  name = "${var.prefix}-${var.environment}-vpc"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs
  intra_subnets   = var.intra_subnet_cidrs

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "production"
  one_nat_gateway_per_az = var.environment == "production"

  enable_dns_hostnames = true
  enable_dns_support   = true

  enable_flow_log                      = true
  create_flow_log_cloudwatch_iam_role  = true
  create_flow_log_cloudwatch_log_group = true

  private_subnet_tags = {
    "kubernetes.io/cluster/${local.cluster_name}" = "owned"
    "kubernetes.io/role/internal-elb"             = "1"
    "karpenter.sh/discovery"                      = local.cluster_name
  }

  public_subnet_tags = {
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                      = "1"
  }
}

# ─── ECR Repository ───────────────────────────────────────────────────
resource "aws_ecr_repository" "platform" {
  name                 = "${var.prefix}-${var.environment}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }
}

resource "aws_ecr_lifecycle_policy" "platform" {
  repository = aws_ecr_repository.platform.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 30 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = { type = "expire" }
    }]
  })
}

# ─── KMS Keys ─────────────────────────────────────────────────────────
resource "aws_kms_key" "eks" {
  description             = "EKS cluster encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "ecr" {
  description             = "ECR encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

# ─── EKS Cluster ──────────────────────────────────────────────────────
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.4"

  cluster_name    = local.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true
  cluster_endpoint_public_access_cidrs = var.allowed_cidr_blocks

  # Encryption
  cluster_encryption_config = {
    resources        = ["secrets"]
    provider_key_arn = aws_kms_key.eks.arn
  }

  # Logging
  cluster_enabled_log_types = ["audit", "api", "authenticator", "controllerManager", "scheduler"]

  # Add-ons
  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Node groups
  eks_managed_node_groups = {
    system = {
      name           = "system"
      instance_types = [var.system_node_type]
      min_size       = 1
      max_size       = 5
      desired_size   = 3
      labels = {
        role = "system"
      }
      taints = [{
        key    = "CriticalAddonsOnly"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
    workloads = {
      name           = "workloads"
      instance_types = var.workload_node_types
      min_size       = var.workload_min_nodes
      max_size       = var.workload_max_nodes
      desired_size   = var.workload_desired_nodes
      labels = {
        role = "workload"
      }
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            encrypted             = true
            kms_key_id            = aws_kms_key.eks.arn
            delete_on_termination = true
          }
        }
      }
    }
  }

  # Karpenter node pools
  node_security_group_tags = {
    "karpenter.sh/discovery" = local.cluster_name
  }

  # Access entries
  enable_cluster_creator_admin_permissions = true
  access_entries = var.access_entries
}

# ─── EBS CSI IRSA ─────────────────────────────────────────────────────
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.33"

  role_name             = "${local.cluster_name}-ebs-csi"
  attach_ebs_csi_policy = true
  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

# ─── Locals ───────────────────────────────────────────────────────────
locals {
  cluster_name = "${var.prefix}-${var.environment}-eks"
  common_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.prefix
    Owner       = var.owner
    CostCenter  = var.cost_center
  }
}
