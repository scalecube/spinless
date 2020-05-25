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

variable "eks-version" {
  default = "1.16"
  type    = string
}

variable "nodePools" {
  default = {
    "pool1" = {
      "count" = 1,
      "minCount" = 1,
      "maxCount" = 2,
      "instanceType" = "t3a.medium",
      "autoscaling": true,
      "taint" = "gateway"
    },
    "pool2" = {
      "count" = 2,
      "minCount" = 2,
      "maxCount" = 4,
      "instanceType" = "t3a.micro",
      "autoscaling": true,
      "taint" = "market-service"
    },
    "pool3" = {
      "count" = 1,
      "minCount" = 1,
      "maxCount" = 2,
      "instanceType" = "t3a.small",
      "autoscaling": true,
      "taint" = "operations"
    }
  }
  type = map
}

variable TF_TOKEN {
  type = string
}