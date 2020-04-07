variable "aws_region" {
  description = "AWS Region"
  default     = "us-east-1"
}

variable "aws_access_key" {
  description = "AWS Access key"
  type        = string
}

variable "aws_secret_access_key" {
  description = "AWS Secret key"
  type        = string
}

variable "cluster-name" {
  default = "exberry-eks"
  type    = string
}

variable "az1" {
  description = "First AZ for EKS"
  default     = "us-east-1a"
  type        = string
}

variable "az2" {
  description = "Second AZ for EKS"
  default     = "us-east-1b"
  type        = string
}

variable "kube_nodes_amount" {
  description = "Kubernetes nodes count"
  default     = 2
  type        = number
}

variable "kube_nodes_instance_type" {
  description = "Kubernetes nodes instance type"
  default     = "t3a.medium"
  type        = string
}
