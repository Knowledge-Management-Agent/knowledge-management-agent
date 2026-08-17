module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version

  # PoC convenience -- a stricter setup would restrict this to a VPN/office
  # CIDR. Matches DEPLOY-10 (namespace-scoped, non-HA PoC is acceptable).
  cluster_endpoint_public_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  enable_cluster_creator_admin_permissions = true

  # Cluster-admin for the human operators of this project, independent of
  # whoever/whatever actually ran `terraform apply` (the CI role, in the
  # GitHub Actions case) -- enable_cluster_creator_admin_permissions above
  # only covers the creator, not these two.
  access_entries = {
    asadulla = {
      principal_arn = "arn:aws:iam::893431614084:user/asadulla"
      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
    jb = {
      principal_arn = "arn:aws:iam::893431614084:user/jb"
      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
    # aws-ebs-csi-driver is added in addons.tf once its IRSA role exists --
    # it needs module.eks.oidc_provider_arn, which doesn't exist until the
    # cluster itself is created.
  }

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      capacity_type  = "ON_DEMAND"
      desired_size   = var.node_desired_size
      min_size       = var.node_min_size
      max_size       = var.node_max_size
    }
  }
}
