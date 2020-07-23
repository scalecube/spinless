module "env-1" {
//  source = "git@github.com:exberry-io/terraform-eks-exberry-tenant.git?ref=v0.1"
  source = "git@github.com:{{ repository }}.git?ref={{ version }}"
}

