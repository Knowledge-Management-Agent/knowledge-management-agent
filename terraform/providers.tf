provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "km-agent"
      ManagedBy = "terraform"
    }
  }
}

# Cluster must exist before kubernetes/helm providers can authenticate against
# it -- the depends_on chain through module.eks in addons.tf enforces that
# ordering; these data/provider blocks just describe *how* to authenticate.
data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}
