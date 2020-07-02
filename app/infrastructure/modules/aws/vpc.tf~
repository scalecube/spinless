data "aws_availability_zones" "available" {}

resource "aws_vpc" "kube_vpc" {
  cidr_block = "10.${var.network_id}.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support = true

  tags = {
    Name = var.cluster-name
  }
}

resource "aws_internet_gateway" "public_subnet_gateway" {
  vpc_id = aws_vpc.kube_vpc.id
}

resource "aws_route" "public_route" {
  route_table_id = aws_vpc.kube_vpc.main_route_table_id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id = aws_internet_gateway.public_subnet_gateway.id
}

resource "aws_subnet" "public" {

  count             = 2
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = "${cidrsubnet("10.${var.network_id}.0.0/16", 4, count.index)}"
  vpc_id            = aws_vpc.kube_vpc.id

  tags = {
    "Name"                                      = "public-subnet-${count.index + 0}"
    "kubernetes.io/cluster/${var.cluster-name}" = "shared"
  }
}

resource "aws_route_table" "public_subnet_route_table" {
  vpc_id = aws_vpc.kube_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.public_subnet_gateway.id
  }
}

resource "aws_route" "public_peering_route" {
  route_table_id            = aws_route_table.public_subnet_route_table.id
  destination_cidr_block    = var.nebula_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.exberry.id
}

resource "aws_route" "nebula_public_peering_route" {
  route_table_id            = var.nebula_route_table_id
  destination_cidr_block    = aws_vpc.kube_vpc.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.exberry.id
}

resource "aws_subnet" "kube" {

  count             = 2
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = "${cidrsubnet("10.${var.network_id}.0.0/16", 4, 2 + 2 * count.index)}"
  vpc_id            = aws_vpc.kube_vpc.id

  tags = {
    "Name"                                      = "eks-01-subnet-${count.index + 0}"
    "kubernetes.io/cluster/${var.cluster-name}" = "shared"
  }
}

resource "aws_eip" "kube_eip" {
  count            = 2
  vpc              = true
}

resource "aws_nat_gateway" "nat_gateway_for_private_subnetworks" {
  count         = 2
  allocation_id = aws_eip.kube_eip[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "NAT"
  }
}

resource "aws_route_table" "eks_route_table" {
  vpc_id = aws_vpc.kube_vpc.id
}

//resource "aws_route" "eks_route" {
//  route_table_id            = aws_route_table.eks_route_table.id
//  destination_cidr_block    = var.nebula_cidr_block
//  nat_gateway_id            = aws_nat_gateway.nat_gateway_for_private_subnetworks[1].id
//}

resource "aws_route" "eks_peering_route" {
  route_table_id            = aws_route_table.eks_route_table.id
  destination_cidr_block    = var.nebula_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.exberry.id
}

//resource "aws_route" "nebula_private_route" {
//  route_table_id            = var.nebula_route_table_id
//  destination_cidr_block    = aws_vpc.kube_vpc.cidr_block
//  vpc_peering_connection_id = aws_vpc_peering_connection.exberry.id
//}

resource "aws_route_table_association" "eks_rta" {
  count          = 2
  subnet_id      = "${element(aws_subnet.kube.*.id, count.index)}"
  route_table_id = aws_route_table.eks_route_table.id
}
