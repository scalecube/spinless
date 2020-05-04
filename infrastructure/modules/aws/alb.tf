resource "aws_security_group" "traefik" {
  name        = "traefik-sg"
  description = "Application load balancer -> traefik"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "Name"      = "alb-traefik"
  }

}

resource "aws_security_group_rule" "alb-ingress-access-https" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik.id
  to_port                  = 443
  type                     = "ingress"
}

resource "aws_security_group_rule" "alb-ingress-access-http" {
  description              = "Allow clients instances to communicate with the ALB"
  from_port                = 80
  protocol                 = "tcp"
  security_group_id        = aws_security_group.traefik.id
  to_port                  = 80
  type                     = "ingress"
}

resource "aws_alb" "alb" {
  name            = "traefik-${var.cluster-name}"
  subnets         = [aws_subnet.public.id, aws_subnet.public2.id]
  security_groups = [aws_security_group.traefik.id]
  internal        = false

  tags = {
    Name    = "alb-traefik-${var.cluster-name}"
  }
}

resource "aws_alb_listener" "alb_listener" {
  load_balancer_arn = aws_alb.alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    target_group_arn = aws_alb_target_group.traefik_target_group.arn
    type             = "forward"
  }
}

resource "aws_alb_listener_rule" "listener_rule" {
  depends_on   = [aws_alb_target_group.traefik_target_group]
  listener_arn = aws_alb_listener.alb_listener.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.traefik_target_group.arn
  }
  condition {
    field  = "path-pattern"
    values = ["/*"]
  }
}

resource "aws_alb_target_group" "traefik_target_group" {
  name     = "target-${var.cluster-name}"
  port     = 30003
  protocol = "HTTP"
  vpc_id   = aws_vpc.kube_vpc.id
  tags = {
    name = "target-${var.cluster-name}"
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

resource "aws_autoscaling_attachment" "traefik_asg_attachment" {
  alb_target_group_arn   = aws_alb_target_group.traefik_target_group.arn
  autoscaling_group_name = "asg-eks-operations-${var.cluster-name}"
}