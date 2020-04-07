data "aws_availability_zones" "available" {}

resource "aws_vpc" "kube_vpc" {
  cidr_block = "10.10.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support = true

  tags = {
    Name = "kube_vpc"
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

  availability_zone = var.az1
  cidr_block        = "10.10.32.0/20"
  vpc_id            = aws_vpc.kube_vpc.id

  tags = {
    Name = "public-subnet"
    "kubernetes.io/cluster/${var.cluster-name}" = shared
  }
}

resource "aws_route_table" "public_subnet_route_table" {
  vpc_id = aws_vpc.kube_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.public_subnet_gateway.id
  }
}

resource "aws_subnet" "kube01" {

  availability_zone = var.az1
  cidr_block        = "10.10.1.0/20"
  vpc_id            = aws_vpc.kube_vpc.id

  tags = {
    Name = "eks-01-subnet"
    "kubernetes.io/cluster/${var.cluster-name}" = shared
  }
}

resource "aws_subnet" "kube02" {

  availability_zone = var.az2
  cidr_block        = "10.10.16.0/20"
  vpc_id            = aws_vpc.kube_vpc.id

  tags = {
    Name = "eks-02-subnet"
    "kubernetes.io/cluster/${var.cluster-name}" = shared
  }
}

resource "aws_eip" "private_subnetworks_nat_ip" {}

resource "aws_nat_gateway" "nat_gateway_for_private_subnetworks" {
  allocation_id = aws_eip.private_subnetworks_nat_ip.id
  subnet_id = aws_subnet.public.id

  tags = {
    Name = "NAT"
  }
}

resource "aws_route_table" "eks_route_table" {
  vpc_id = aws_vpc.kube_vpc.id
}

resource "aws_route" "eks_route" {
  route_table_id = aws_route_table.eks_route_table.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id = aws_nat_gateway.nat_gateway_for_private_subnetworks.id
}

resource "aws_route_table_association" "eks_rta01" {

  subnet_id      = aws_subnet.kube01.id
  route_table_id = aws_route_table.eks_route_table.id
}

resource "aws_route_table_association" "eks_rta02" {

  subnet_id      = aws_subnet.kube02.id
  route_table_id = aws_route_table.eks_route_table.id
}
