resource "aws_security_group" "traefik-alb-discovery" {
  name        = "traefik-sg-alb-discovery"
  description = "Application discovery load balancer-traefik"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "Name"      = "alb-discovery-traefik"
  }

  timeouts {
    create = "60m"
    delete = "60m"
  }

}

resource "aws_security_group" "traefik-alb-transport" {
  name        = "traefik-sg-alb-transport"
  description = "Application transport load balancer-traefik"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "Name" = "alb-transport-traefik"
  }

  timeouts {
    create = "60m"
    delete = "60m"
  }

}

resource "aws_security_group" "traefik-alb-ext" {
  name        = "traefik-sg-alb-ext"
  description = "Application external load balancer-traefik"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "Name"      = "alb-ext-traefik"
  }

  timeouts {
    create = "60m"
    delete = "60m"
  }

}

resource "aws_security_group_rule" "alb-ext-ingress-access-https" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik-alb-ext.id
  to_port                  = 443
  type                     = "ingress"
  cidr_blocks              = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb-ext-ingress-access-http" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 80
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik-alb-ext.id
  to_port                  = 80
  type                     = "ingress"
  cidr_blocks              = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb-discovery-ingress-access-https" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik-alb-discovery.id
  to_port                  = 443
  type                     = "ingress"
  cidr_blocks              = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb-discovery-ingress-access-http" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 80
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik-alb-discovery.id
  to_port                  = 80
  type                     = "ingress"
  cidr_blocks              = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb-transport-ingress-access-https" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik-alb-transport.id
  to_port                  = 443
  type                     = "ingress"
  cidr_blocks              = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb-transport-ingress-access-http" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 80
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik-alb-transport.id
  to_port                  = 80
  type                     = "ingress"
  cidr_blocks              = ["0.0.0.0/0"]
}

resource "aws_alb" "alb-ext" {
  name            = "traefik-${var.cluster-name}-ext"
  subnets         = "${aws_subnet.public.*.id}"
  security_groups = [aws_security_group.traefik-alb-ext.id]
  internal        = false

  tags = {
    Name    = "alb-traefik-${var.cluster-name}-ext"
  }

  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }

}

resource "aws_alb" "alb-transport" {
  name            = "traefik-${var.cluster-name}-transport"
  subnets         = "${aws_subnet.kube.*.id}"
  security_groups = [aws_security_group.traefik-alb-transport.id]
  internal        = true

  tags = {
    Name = "alb-traefik-${var.cluster-name}-transport"
  }

  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }

}

resource "aws_alb" "alb-discovery" {
  name            = "traefik-${var.cluster-name}-discovery"
  subnets         = "${aws_subnet.kube.*.id}"
  security_groups = [aws_security_group.traefik-alb-discovery.id]
  internal        = true

  tags = {
    Name = "alb-traefik-${var.cluster-name}-discovery"
  }

  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }

}

resource "aws_alb_listener" "alb_listener_ext" {
  load_balancer_arn = aws_alb.alb-ext.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    target_group_arn = aws_alb_target_group.traefik_target_group_ext.arn
    type             = "forward"
  }
}

resource "aws_alb_listener" "alb_listener_discovery" {
  load_balancer_arn = aws_alb.alb-discovery.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    target_group_arn = aws_alb_target_group.traefik_target_group_discovery.arn
    type             = "forward"
  }
}

resource "aws_alb_listener" "alb_listener_transport" {
  load_balancer_arn = aws_alb.alb-transport.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    target_group_arn = aws_alb_target_group.traefik_target_group_transport.arn
    type             = "forward"
  }
}

resource "aws_alb_listener_rule" "listener_rule" {
  depends_on   = [aws_alb_target_group.traefik_target_group_ext]
  listener_arn = aws_alb_listener.alb_listener_ext.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.traefik_target_group_ext.arn
  }
  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}

resource "aws_alb_listener_rule" "listener_rule_transport" {
  depends_on   = [aws_alb_target_group.traefik_target_group_transport]
  listener_arn = aws_alb_listener.alb_listener_transport.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.traefik_target_group_transport.arn
  }
  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}

resource "aws_alb_listener_rule" "listener_rule_discovery" {
  depends_on   = [aws_alb_target_group.traefik_target_group_discovery]
  listener_arn = aws_alb_listener.alb_listener_discovery.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.traefik_target_group_discovery.arn
  }
  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}

resource "aws_alb_target_group" "traefik_target_group_ext" {
  name     = "target-${var.cluster-name}-ext"
  port     = 30003
  protocol = "HTTP"
  vpc_id   = aws_vpc.kube_vpc.id
  tags = {
    name = "target-${var.cluster-name}-ext"
  }

  health_check {
    healthy_threshold   = 3
    unhealthy_threshold = 10
    timeout             = 5
    interval            = 10
    path                = "/"
    port                = "30003"
    matcher             = 404
  }
}

resource "aws_alb_target_group" "traefik_target_group_discovery" {
  name     = "target-${var.cluster-name}-discovery"
  port     = 30004
  protocol = "HTTP"
  vpc_id   = aws_vpc.kube_vpc.id
  tags = {
    name = "target-${var.cluster-name}-discovery"
  }

  health_check {
    healthy_threshold   = 3
    unhealthy_threshold = 10
    timeout             = 5
    interval            = 10
    path                = "/"
    port                = "30004"
    matcher             = 404
  }
}

resource "aws_alb_target_group" "traefik_target_group_transport" {
  name     = "target-${var.cluster-name}-transport"
  port     = 30005
  protocol = "HTTP"
  vpc_id   = aws_vpc.kube_vpc.id
  tags = {
    name = "target-${var.cluster-name}-transport"
  }

  health_check {
    healthy_threshold   = 3
    unhealthy_threshold = 10
    timeout             = 5
    interval            = 10
    path                = "/"
    port                = "30005"
    matcher             = 404
  }
}

resource "aws_autoscaling_attachment" "traefik_asg_attachment_ext" {
  alb_target_group_arn   = aws_alb_target_group.traefik_target_group_ext.arn
  autoscaling_group_name = aws_autoscaling_group.nodePool["kubsystem"].id
}

resource "aws_autoscaling_attachment" "traefik_asg_attachment_transport" {
  alb_target_group_arn   = aws_alb_target_group.traefik_target_group_transport.arn
  autoscaling_group_name = aws_autoscaling_group.nodePool["kubsystem"].id
}

resource "aws_autoscaling_attachment" "traefik_asg_attachment_discovery" {
  alb_target_group_arn   = aws_alb_target_group.traefik_target_group_discovery.arn
  autoscaling_group_name = aws_autoscaling_group.nodePool["kubsystem"].id
}
