# Requester's side of the connection cluster
resource "aws_vpc_peering_connection" "exberry" {
  vpc_id        = "${aws_vpc.kube_vpc.id}"
  peer_vpc_id   = "${var.peer_vpc_id}"
  peer_owner_id = "${var.peer_account_id}"
  peer_region   = "${var.aws_region}"
  auto_accept   = false

  tags = {
    Side = "Requester"
  }
}

# Accepter's side of the connection cluster
resource "aws_vpc_peering_connection_accepter" "peer" {
  vpc_peering_connection_id = "${aws_vpc_peering_connection.exberry.id}"
  auto_accept               = true

  tags = {
    Side = "Accepter"
  }
}