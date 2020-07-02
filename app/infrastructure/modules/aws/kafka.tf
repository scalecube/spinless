resource "aws_security_group" "msk" {
  count = "${var.cluster_type == "ops" ? 1 : 0}"
  name = "kafka-${var.cluster-name}"
  description = "Security group for kafka db in the cluster"
  vpc_id      = aws_vpc.kube_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "Name"                                             = "kafka"
    "kubernetes.io/cluster/${var.cluster-name}"        = "shared"
  }
}

resource "aws_security_group_rule" "msk-access" {
  count = "${var.cluster_type == "ops" ? 1 : 0}"
  description              = "Allow VPC instances to access kafka"
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.msk[count.index].id
  source_security_group_id              = aws_security_group.eks-node.id
  to_port                  = 0
  type                     = "ingress"
}

resource "aws_msk_configuration" "unlim-logs" {
  count = "${var.cluster_type == "ops" ? 1 : 0}"
  kafka_versions = ["2.2.1"]
  name           = "unlim-logs-${var.cluster-name}"

  server_properties = <<PROPERTIES
auto.create.topics.enable=false
default.replication.factor=3
min.insync.replicas=2
num.io.threads=8
num.network.threads=5
num.partitions=1
num.replica.fetchers=2
socket.request.max.bytes=104857600
unclean.leader.election.enable=true
log.retention.bytes=-1
log.retention.ms=-1
PROPERTIES
}

resource "aws_msk_cluster" "kafka" {
  count = "${var.cluster_type == "ops" && var.aws_region == "eu-west-2" ? 1 : 0}"
  cluster_name           = "kafka-${var.cluster-name}"
  kafka_version          = "2.2.1"
  number_of_broker_nodes = 2

  broker_node_group_info {
    instance_type   = "kafka.t3.small"
    ebs_volume_size = 10
    client_subnets = "${aws_subnet.public.*.id}"
    security_groups = ["${aws_security_group.msk[count.index].id}"]
  }

  client_authentication {
    tls {
      certificate_authority_arns = [ "arn:aws:acm-pca:eu-west-2:539924900246:certificate-authority/42774d82-9c65-41ee-a384-cf929c32768b" ]
    }
  }

  configuration_info {
    revision = "${aws_msk_configuration.unlim-logs[count.index].latest_revision}"
    arn = "${aws_msk_configuration.unlim-logs[count.index].arn}"
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster = true
    }
  }

  tags = {
    client = "${var.cluster-name}"
  }
}
