resource "aws_security_group" "eks-node" {
  name = "workers-${var.cluster-name}"
  description = "Security group for all nodes in the cluster"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "name"                                             = "aws-security-group-${var.cluster-name}-eks-node"
    "kubernetes.io/cluster/${var.cluster-name}"        = "shared"
  }
}

resource "aws_security_group_rule" "eks-node-access-vpc" {
  description              = "Allow VPC instances to communicate with the cluster API Server"
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.eks-node.id
  cidr_blocks              = ["10.${var.network_id}.0.0/16"]
  to_port                  = 0
  type                     = "ingress"
}

resource "aws_security_group_rule" "node-ingress-self" {
  description              = "Allow node to communicate with each other"
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.eks-node.id
  source_security_group_id = aws_security_group.eks-node.id
  to_port                  = 65535
  type                     = "ingress"
}

resource "aws_security_group_rule" "node-ingress-cluster" {
  description              = "Allow worker Kubelets and pods to receive communication from the cluster control plane"
  from_port                = 1025
  protocol                 = "tcp"
  security_group_id        = aws_security_group.eks-node.id
  source_security_group_id = aws_security_group.eks-master.id
  to_port                  = 65535
  type                     = "ingress"
}
