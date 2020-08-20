terraform {
  backend "s3" {
    bucket = "{{ bucket }}"
    key    = "{{ resource_path }}/terraform.tfstate"
    region = "{{ region }}"
    access_key = "{{ access_key }}"
    secret_key = "{{ secret_key }}"
    {% if role_arn %}
    role_arn = "{{ role_arn  }}"
    {% endif %}
    dynamodb_table = "{{ dynamodb_table }}"
  }
}