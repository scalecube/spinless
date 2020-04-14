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
/*
locals {
  for_each = var.nodePools

  eks-node-userdata-"${each.value[\"taint\"]}" = <<USERDATA
#!/bin/bash
set -o xtrace
/etc/eks/bootstrap.sh --apiserver-endpoint '${aws_eks_cluster.eks.endpoint}' --kubelet-extra-args '--register-with-taints="type=${each.value[\"taint\"]}:NoSchedule"'  --b64-cluster-ca '${aws_eks_cluster.eks.certificate_authority[0].data}' '${var.cluster-name}'
USERDATA

}
*/


resource "aws_launch_configuration" "nodes_configuration" {
  for_each                    = var.nodePools

  name                        = "aws_lc_${each.key}"
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.eks-node.name
  image_id                    = data.aws_ami.eks-worker.id
  instance_type               = each.value["instanceType"]
/*
name_prefix                 = "eks-${each.key}"
*/
key_name                    = "kube_test"
  security_groups  = [aws_security_group.eks-node.id]

/*
  user_data_base64 = base64encode(local.eks-node-userdata-${each.value["taint"]})
*/

  user_data_base64            = base64encode(<<USERDATA
#!/bin/bash
set -o xtrace
/etc/eks/bootstrap.sh --apiserver-endpoint '${aws_eks_cluster.eks.endpoint}' --kubelet-extra-args '--register-with-taints="type=${each.value["taint"]}"'  --b64-cluster-ca '${aws_eks_cluster.eks.certificate_authority.0.data}' '${var.cluster-name}'
USERDATA
)


  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "eks-t3a-medium" {
  for_each             = var.nodePools

  desired_capacity     = each.value["count"]
  launch_configuration = "aws_lc_${each.key}"
  max_size             = each.value["maxCount"]
  min_size             = each.value["minCount"]
  name                 = "asg-eks-${each.value["taint"]}"
  vpc_zone_identifier  = [aws_subnet.kube01.id]

  tag {
    key                 = "Name"
    value               = "asg-eks-${each.value["instanceType"]}"
    propagate_at_launch = true
  }

  tag {
    key                 = "kubernetes.io/cluster/${var.cluster-name}"
    value               = "shared"
    propagate_at_launch = true
  }

  tag {
    key                 = "k8s.io/cluster-autoscaler/enabled"
    value               = "true"
    propagate_at_launch = true
  }

  tag {
    key                 = "k8s.io/cluster-autoscaler/${var.cluster-name}"
    value               = "true"
    propagate_at_launch = true
  }

  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/taint/type"
    value               = each.value["taint"]
    propagate_at_launch = true
  }

}
