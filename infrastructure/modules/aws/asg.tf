data "aws_ami" "eks-worker" {
   filter {
     name   = "name"
     values = ["amazon-eks-node-1*"]
   }

   most_recent = true
   owners      = ["602401143452"] # Amazon EKS AMI Account ID
 }

data "aws_region" "current" {
}

locals {
  eks-node-userdata = <<USERDATA
#!/bin/bash
set -o xtrace
/etc/eks/bootstrap.sh --apiserver-endpoint '${aws_eks_cluster.eks.endpoint}' --b64-cluster-ca '${aws_eks_cluster.eks.certificate_authority[0].data}' '${var.cluster-name}'
USERDATA

}

resource "aws_launch_configuration" "nodes_configuration" {
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.eks-node.name
  image_id                    = data.aws_ami.eks-worker.id
  instance_type               = var.kube_nodes_instance_type
  name_prefix                 = "eks"
  key_name                    = "kube_test"
  security_groups  = [aws_security_group.eks-node.id]
  user_data_base64 = base64encode(local.eks-node-userdata)

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "eks-t3a-medium" {
  desired_capacity     = 1
  launch_configuration = aws_launch_configuration.nodes_configuration.id
  max_size             = var.kube_nodes_amount
  min_size             = 1
  name                 = "asg-eks-t3a-medium"
  vpc_zone_identifier = [aws_subnet.kube01.id]

  tag {
    key                 = "Name"
    value               = "asg-eks-t3a-medium"
    propagate_at_launch = true
  }

  tag {
    key                 = "kubernetes.io/cluster/${var.cluster-name}"
    value               = "shared"
    propagate_at_launch = true
  }

}
