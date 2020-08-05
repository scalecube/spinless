terraform {
  backend "s3" {
    bucket = "{{ bucket }}"
    key    = "{{ resource_path }}/terraform.tfstate"
    region = "{{ region }}"
    access_key = "{{ access_key }}"
    secret_key = "{{ secret_key }}"
    role_arn = "{{ role_arn  }}"
    dynamodb_table = "{{ dynamodb_table }}"
  }
}