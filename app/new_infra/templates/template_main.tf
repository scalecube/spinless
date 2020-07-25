module "{{ module_name }}" {
  source = "git@github.com:{{ repository }}.git?ref={{ version }}"
  {% for key in variables %}
  {{ key }} = var.{{ key }}
  {% endfor %}
}

