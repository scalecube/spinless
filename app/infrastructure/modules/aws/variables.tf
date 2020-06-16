variable "aws_region" {
  description = "AWS Region"
  default     = "eu-west-1"
}

variable "aws_access_key" {
  description = "AWS Access key"
  type        = string
}

variable "peer_vpc_id" {
  description = "Network ID"
  type        = string
}

variable "nebula_cidr_block" {
  description = "Nebula CIDR Block"
  type        = string
}

variable "peer_account_id" {
  description = "Network ID"
  type        = string
}

variable "network_id" {
  description = "Network ID"
  type        = string
}

variable "nebula_route_table_id" {
  description = "Nebula Route Table ID"
  type        = string
}

variable "availability_zone" {
  description = "Availability Zone"
  default     = "us-east-1a"
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
  default     = {
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
  type        = map
}