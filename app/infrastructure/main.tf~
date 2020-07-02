module "aws" {
  source = "./modules/aws"

  aws_region            = var.aws_region
  aws_access_key        = var.aws_access_key
  aws_secret_key        = var.aws_secret_key
  cluster-name          = var.cluster-name
  eks-version           = var.eks-version
  nodePools             = var.nodePools
  nebula_cidr_block     = var.nebula_cidr_block
  network_id            = var.network_id
  peer_vpc_id           = var.peer_vpc_id
  peer_account_id       = var.peer_account_id
  nebula_route_table_id = var.nebula_route_table_id
}
