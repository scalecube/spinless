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
}

resource "aws_security_group" "traefik-alb-int" {
  name        = "traefik-sg-alb-int"
  description = "Application internal load balancer-traefik"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "Name" = "alb-int-traefik"
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

resource "aws_security_group_rule" "alb-int-ingress-access" {
  description       = "Allow clients instances to communicate with the ALB"
  from_port         = 0
  protocol          = "-1"
  security_group_id = aws_security_group.traefik-alb-int.id
  to_port           = 0
  type              = "ingress"
  cidr_blocks       = ["10.0.0.0/8"]
}

resource "aws_alb" "alb-ext" {
  name            = "traefik-${var.cluster-name}-ext"
  subnets         = "${aws_subnet.public.*.id}"
  security_groups = [aws_security_group.traefik-alb-ext.id]
  internal        = false

  tags = {
    Name    = "alb-traefik-${var.cluster-name}-ext"
  }
}

resource "aws_alb" "alb-int" {
  name            = "traefik-${var.cluster-name}-int"
  subnets         = "${aws_subnet.private.*.id}"
  security_groups = [aws_security_group.traefik-alb-int.id]
  internal        = true

  tags = {
    Name = "alb-traefik-${var.cluster-name}-ext"
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

resource "aws_alb_listener" "alb_listener_int" {
  load_balancer_arn = aws_alb.alb-int.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    target_group_arn = aws_alb_target_group.traefik_target_group_int.arn
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

resource "aws_alb_listener_rule" "listener_rule_int" {
  depends_on   = [aws_alb_target_group.traefik_target_group_int]
  listener_arn = aws_alb_listener.alb_listener_int.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.traefik_target_group_int.arn
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

resource "aws_alb_target_group" "traefik_target_group_int" {
  name     = "target-${var.cluster-name}-int"
  port     = 30004
  protocol = "HTTP"
  vpc_id   = aws_vpc.kube_vpc.id
  tags = {
    name = "target-${var.cluster-name}-int"
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

resource "aws_autoscaling_attachment" "traefik_asg_attachment_ext" {
  alb_target_group_arn   = aws_alb_target_group.traefik_target_group_ext.arn
  autoscaling_group_name = aws_autoscaling_group.nodePool["kubsystem"].id
}

resource "aws_autoscaling_attachment" "traefik_asg_attachment_int" {
  alb_target_group_arn   = aws_alb_target_group.traefik_target_group_int.arn
  autoscaling_group_name = aws_autoscaling_group.nodePool["kubsystem"].id
}
