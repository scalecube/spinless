terraform {
  backend "local" {
    path = "../state/tfstate/terraform.tfstate"
  }
}
