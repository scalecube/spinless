resource "random_password" "pass" {
  length = 16
  special = false
  number = true
}

resource "aws_security_group" "rds-psql" {
  count = "${var.cluster_type == "ops" ? 1 : 0}"
  name = "psql-${var.cluster-name}"
  description = "Security group for psql db in the cluster"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "Name"                                             = "rds-psql"
    "kubernetes.io/cluster/${var.cluster-name}"        = "shared"
  }
}

resource "aws_security_group_rule" "rds-psql-access" {
  count = "${var.cluster_type == "ops" ? 1 : 0}"
  description              = "Allow VPC instances to access DB"
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.rds-psql[count.index].id
  source_security_group_id              = aws_security_group.eks-node.id
  to_port                  = 0
  type                     = "ingress"
}

resource "aws_db_subnet_group" "primary" {
  count = "${var.cluster_type == "ops" ? 1 : 0}"
  name       = "psql-main"
  subnet_ids = "${aws_subnet.kube.*.id}"

  tags = {
    Name = "PSQL DB subnet group"
  }
}

resource "aws_db_instance" "ex-data" {
  count = "${var.cluster_type == "ops" ? 1 : 0}"
  allocated_storage    = 20
  max_allocated_storage = 100
  allow_major_version_upgrade = false
  auto_minor_version_upgrade = false
  backup_retention_period = 28
  backup_window = "04:58-05:28"
  copy_tags_to_snapshot = true
  storage_type         = "gp2"
  engine               = "postgres"
  engine_version       = "11.4"
  instance_class       = "db.t3.medium"
  name                 = "exchange"
  username             = "${var.db_user}"
  password = "${random_password.pass.result}"
  identifier = "exchange-${var.cluster-name}"
  vpc_security_group_ids = [
    "${aws_security_group.rds-psql[count.index].id}"
        ]
  db_subnet_group_name = aws_db_subnet_group.primary[count.index].id
  maintenance_window = "sat:00:27-sat:02:57"
  multi_az = false
  port = 5432
  skip_final_snapshot = true
}
