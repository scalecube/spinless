data "aws_ssm_parameter" "eks_node" {
  name = "/aws/service/eks/optimized-ami/1.16/amazon-linux-2/recommended/image_id"
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

  name                        = "aws_lc_peer_${each.key}_${var.cluster-name}"
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.eks-node.name
  image_id                    = data.aws_ssm_parameter.eks_node.value
  instance_type               = each.value["instanceType"]
  key_name                    = "kube_test"
  security_groups             = [aws_security_group.eks-node.id]

  root_block_device {
    volume_type           = "gp2"
    volume_size           = 100
    delete_on_termination = true
  }

/*
  user_data_base64 = base64encode(local.eks-node-userdata-${each.value["taint"]})
*/

  user_data_base64            = base64encode(<<USERDATA
#!/bin/bash
set -o xtrace
yum update && yum install ec2-net-utils -y
service network restart
/etc/eks/bootstrap.sh --apiserver-endpoint '${aws_eks_cluster.eks.endpoint}' --kubelet-extra-args '--register-with-taints="type=${each.value["taint"]}:NoSchedule"'  --b64-cluster-ca '${aws_eks_cluster.eks.certificate_authority.0.data}' '${var.cluster-name}'
USERDATA
)


  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "nodePool" {
  for_each             = var.nodePools

  desired_capacity     = each.value["count"]
  launch_configuration = "aws_lc_peer_${each.key}_${var.cluster-name}"
  max_size             = each.value["maxCount"]
  min_size             = each.value["minCount"]
  name                 = "asg-eks-${each.value["taint"]}-${var.cluster-name}"
  vpc_zone_identifier  = "${aws_subnet.kube.*.id}"

  depends_on = [aws_launch_configuration.nodes_configuration]

  tag {
    key                 = "Name"
    value               = "asg-eks-${each.value["instanceType"]}-${var.cluster-name}"
    propagate_at_launch = true
  }

  tag {
    key                 = "kubernetes.io/cluster/${var.cluster-name}"
    value               = "shared"
    propagate_at_launch = true
  }

  tag {
    key                 =  each.value["autoscaling"] == true ? "k8s.io/cluster-autoscaler/enabled" : "k8s.io/cluster-autoscaler/disabled"
    value               = "true"
    propagate_at_launch = true
  }

  tag {
    key                 = each.value["autoscaling"] == true ? "k8s.io/cluster-autoscaler/${var.cluster-name}" : "k8s.io/cluster-autoscaler/off"
    value               = "true"
    propagate_at_launch = true
  }

  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/taint/type"
    value               = each.value["taint"]
    propagate_at_launch = true
  }

  timeouts {
    delete = "60m"
  }
}
