data "aws_availability_zones" "available" {}

resource "aws_vpc" "kube_vpc" {
  cidr_block           = "10.${var.network_id}.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  name                 = "aws-vpc-${var.cluster-name}-kube"

  tags = {
    name = "aws-vpc-${var.cluster-name}-kube"
  }
}

resource "aws_internet_gateway" "public_subnet_gateway" {
  vpc_id = aws_vpc.kube_vpc.id
  name   = "aws-internet-gateway-${var.cluster-name}"
}

resource "aws_route" "public_route" {
  route_table_id         = aws_vpc.kube_vpc.main_route_table_id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.public_subnet_gateway.id
}

resource "aws_subnet" "public" {

  count             = 2
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = "${cidrsubnet("10.${var.network_id}.0.0/16", 4, count.index)}"
  vpc_id            = aws_vpc.kube_vpc.id
  name              = "aws-subnet-${var.cluster-name}-public"

  tags = {
    "name"                                      = "public-subnet-${var.cluster-name}-${count.index + 0}"
    "kubernetes.io/cluster/${var.cluster-name}" = "shared"
  }
}

resource "aws_route_table" "public_subnet_route_table" {
  vpc_id = aws_vpc.kube_vpc.id
  name   = "aws-route-table-${var.cluster-name}-public-subnet"
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.public_subnet_gateway.id
  }
}

resource "aws_subnet" "kube" {

  count             = 2
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = "${cidrsubnet("10.${var.network_id}.0.0/16", 4, 2 + 2 * count.index)}"
  vpc_id            = aws_vpc.kube_vpc.id
  name              = "aws-subnet-${var.cluster-name}-kube"

  tags = {
    "name"                                      = "eks-kube-subnet-${var.cluster-name}-${count.index + 0}"
    "kubernetes.io/cluster/${var.cluster-name}" = "shared"
  }
}

resource "aws_eip" "kube_eip" {
  vpc              = true
}

resource "aws_nat_gateway" "nat_gateway_for_private_subnetworks" {
  count         = 1
  allocation_id = aws_eip.kube_eip.id
  subnet_id     = aws_subnet.public[count.index].id
  name          = "aws-nat-gateway-${var.cluster-name}"

  tags = {
    "name" = "nat-gateway-${var.cluster-name}"
  }
}

resource "aws_route_table" "eks_route_table" {
  vpc_id = aws_vpc.kube_vpc.id
  name   = "aws-route-table-${var.cluster-name}-kube-subnet"
}

resource "aws_route" "eks_route" {
  count = 1
  route_table_id            = aws_route_table.eks_route_table.id
  destination_cidr_block    = "0.0.0.0/0"
  nat_gateway_id            = aws_nat_gateway.nat_gateway_for_private_subnetworks[count.index].id
}

resource "aws_route_table_association" "eks_rta" {
  count          = 2
  subnet_id      = "${element(aws_subnet.kube.*.id, count.index)}"
  route_table_id = aws_route_table.eks_route_table.id
}
