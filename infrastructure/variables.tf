variable "aws_region" {
  description = "AWS Region"
  default     = "us-east-1"
}

variable "aws_access_key" {
  description = "AWS Access key"
  type        = string
}

variable "aws_secret_key" {
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

variable "nodePools" {
  description = "ASG"
  default     = {
        "pool1" = {
          "count" = 1,
          "minCount" = 1,
          "maxCount" = 2,
          "instanceType" = "t3a.medium",
          "taint" = "gateway"
        },
        "pool2" = {
          "count" = 2,
          "minCount" = 2,
          "maxCount" = 4,
          "instanceType" = "t3a.micro",
          "taint" = "market-service"
        },
        "pool3" = {
          "count" = 1,
          "minCount" = 1,
          "maxCount" = 2,
          "instanceType" = "t3a.small",
          "taint" = "seed"
        }
      }
  type        = map
}
