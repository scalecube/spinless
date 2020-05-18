resource "aws_eks_cluster" "eks" {
  name            = var.cluster-name
  role_arn        = aws_iam_role.eks-cluster-role.arn
  version         = var.eks-version

  vpc_config {
    endpoint_private_access = true
    endpoint_public_access = true
    security_group_ids = [aws_security_group.eks-master.id]
    subnet_ids         = [aws_subnet.public.id, aws_subnet.kube01.id, aws_subnet.kube02.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks-AmazonEKSClusterPolicy,
    aws_iam_role_policy_attachment.eks-AmazonEKSServicePolicy
  ]
}

output "endpoint" {
  value = aws_eks_cluster.eks.endpoint
}

output "kubeconfig-certificate-authority-data" {
  value = aws_eks_cluster.eks.certificate_authority.0.data
}

locals {
  config_map_aws_auth = <<CONFIGMAPAWSAUTH


apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth
  namespace: kube-system
data:
  mapRoles: |
    - rolearn: aws_iam_role.eks-node.arn
      username: system:node:{{EC2PrivateDNSName}}
      groups:
        - system:bootstrappers
        - system:nodes
CONFIGMAPAWSAUTH

}

output "config_map_aws_auth" {
  value = local.config_map_aws_auth
}

