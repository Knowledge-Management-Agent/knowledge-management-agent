terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.31"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.14"
    }
  }

  # Bucket/table come from terraform/bootstrap's outputs -- initialize with:
  #   terraform init -backend-config=backend.hcl
  # (copy backend.hcl.example to backend.hcl first; backend.hcl is gitignored
  # since it's environment-specific, not secret).
  backend "s3" {}
}
