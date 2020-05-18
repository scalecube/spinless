module "aws" {
  source = "./modules/aws"

  aws_region        = var.aws_region
  aws_access_key    = var.aws_access_key
  aws_secret_key    = var.aws_secret_key
  cluster-name      = var.cluster-name
  eks-version       = var.eks-version
  nodePools         = var.nodePools
}
