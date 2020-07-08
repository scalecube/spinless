resource "aws_security_group" "eks-master" {
  name        = "eks-sg"
  description = "Cluster communication with worker nodes"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name                                               = "${var.cluster-name}-master-eks-security-group"
    "kubernetes.io/cluster/${var.cluster-name}"        = "shared"
  }
}

resource "aws_security_group_rule" "eks-ingress-access" {
  description              = "Allow VPC instances to communicate with the cluster API Server"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.eks-master.id
  source_security_group_id = aws_security_group.eks-node.id
  to_port                  = 443
  type                     = "ingress"
}

resource "aws_security_group_rule" "eks-ingress-vpc" {
  description              = "Allow VPC instances to communicate with the cluster API Server"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.eks-master.id
  cidr_blocks              = ["10.0.0.0/16"]
  to_port                  = 443
  type                     = "ingress"
}
