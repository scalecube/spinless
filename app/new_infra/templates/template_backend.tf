terraform {
  backend "s3" {
    bucket = "{{ bucket }}" # i e exberry-terraform-states-develop
    key    = "states/{{ cluster_name }}/terraform.tfstate" # i e states/cluster_name/terraform.tfstate
    dynamodb_table = "{{ dynamodb_table }}" # // i e terraform-lock
  }
}