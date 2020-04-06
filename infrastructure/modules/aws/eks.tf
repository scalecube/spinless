resource "aws_eks_cluster" "eks" {
  name            = var.cluster-name
  role_arn        = aws_iam_role.eks-cluster-role.arn
  version         = "1.15"

  vpc_config {
    vpc_id = aws_vpc.kube_vpc.id
    endpoint_private_access = true
    endpoint_public_access = false
    security_group_ids = [aws_security_group.eks-master.id]
    subnet_ids         = [aws_subnet.kube01.id, aws_subnet.kube02.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks-AmazonEKSClusterPolicy,
    aws_iam_role_policy_attachment.eks-AmazonEKSServicePolicy
  ]
}