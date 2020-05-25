resource "aws_iam_role" "eks-node" {
  name = "eks-node-role-${var.cluster-name}"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY
}


resource "aws_iam_role_policy" "cluster-autoscaler" {
 name        = "cluster-autoscaler-${var.cluster-name}"
 role = aws_iam_role.eks-node.id

 policy = <<POLICY
{
   "Version": "2012-10-17",
   "Statement": [
     {
           "Effect": "Allow",
           "Action": [
               "autoscaling:DescribeAutoScalingGroups",
               "autoscaling:DescribeAutoScalingInstances",
               "autoscaling:DescribeLaunchConfigurations",
               "autoscaling:SetDesiredCapacity",
               "autoscaling:TerminateInstanceInAutoScalingGroup",
               "autoscaling:DescribeTags"
           ],
           "Resource": "*"
       }
   ]
}
POLICY
}


resource "aws_iam_role_policy_attachment" "eks-node-AmazonEKSWorkerNodePolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role = aws_iam_role.eks-node.name
}

resource "aws_iam_role_policy_attachment" "eks-node-AmazonEKS_CNI_Policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role = aws_iam_role.eks-node.name
}

resource "aws_iam_role_policy_attachment" "eks-node-AmazonEC2ContainerRegistryReadOnly" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role = aws_iam_role.eks-node.name
}

resource "aws_iam_instance_profile" "eks-node" {
  name = "eks-node-${var.cluster-name}"
  role = aws_iam_role.eks-node.name
}
