module "aws" {
  source = "./modules/aws"

  aws_region        = var.aws_region
  aws_access_key    = var.aws_access_key
  aws_secret_key    = var.aws_secret_key
  cluster-name      = var.cluster-name
  az1               = var.az1
  az2               = var.az2
  kube_nodes_amount = var.kube_nodes_amount
}
