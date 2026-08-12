variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "km-agent-poc"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Must be a currently-supported version -- check with `aws eks describe-cluster-versions` before bumping, since AWS periodically retires old versions (1.30 was retired as of this writing, which is what motivated pinning this explicitly rather than leaving it undocumented)."
  type        = string
  default     = "1.34"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC created for this cluster."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs to spread public/private subnets across."
  type        = number
  default     = 2
}

variable "node_instance_types" {
  description = "EC2 instance types for the EKS managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "ecr_repository_names" {
  description = "ECR repositories to create (matches image names used in step.md and k8s/*.yaml)."
  type        = list(string)
  default     = ["km-agent-backend", "km-agent-frontend"]
}

variable "lb_controller_chart_version" {
  description = "aws-load-balancer-controller Helm chart version."
  type        = string
  default     = "1.8.1"
}
