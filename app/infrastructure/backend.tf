terraform {
  backend "remote" {
    organization = "Exberry"
    workspaces {
      prefix = "exberry-"
    }
  }
}