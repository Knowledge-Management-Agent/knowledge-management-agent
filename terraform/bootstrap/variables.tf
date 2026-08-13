variable "region" {
  description = "AWS region for the Terraform state backend resources."
  type        = string
  default     = "us-east-1"
}

variable "state_bucket_name" {
  description = "Globally-unique S3 bucket name for Terraform state. Leave blank to derive one from the AWS account ID (km-agent-tfstate-<account-id>)."
  type        = string
  default     = ""
}

variable "lock_table_name" {
  description = "DynamoDB table name used for Terraform state locking."
  type        = string
  default     = "km-agent-terraform-locks"
}
