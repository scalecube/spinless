cluster-name = "{{ variables.resource_name }}"
network_id = "{{ variables.network_id }}"
certificate_arn_ext = "{{ variables.certificate_arn_ext }}"
cluster_type = "{{ variables.cluster_type }}"
transit_gw_id = "{{ variables.transit_gw_id }}"
head_vpc_id = "{{ variables.head_vpc_id }}"
dns_suffix = "{{ variables.dns_suffix }}"
dns_lb = "{{ variables.dns_lb }}"
nodePools = {{ variables.nodePools }}
{% if variables.eks_version %}
eks-version = "{{ variables.eks_version }}"
{% endif %}
