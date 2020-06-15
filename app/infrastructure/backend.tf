terraform {
  backend "remote" {
    organization = "ORG"
    workspaces {
      prefix = "ORG-"
    }
  }
}
