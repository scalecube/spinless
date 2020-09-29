cluster-name = "{{ variables.resource_name }}"
network_id = "{{ variables.network_id }}"
nebula_cidr_block = "{{ variables.nebula_cidr_block }}"
nebula_route_table_id = "{{ variables.nebula_route_table_id }}"
peer_account_id = "{{ variables.peer_account_id }}"
peer_vpc_id = "{{ variables.peer_vpc_id }}"
certificate_arn_ext = "{{ variables.certificate_arn_ext }}"
certificate_arn_discovery = "{{ variables.certificate_arn_discovery }}"
nodePools = {{ variables.nodePools }}
cluster_type = "{{ variables.cluster_type }}"
transit_gw_id = "{{ variables.transit_gw_id }}"
ops_vpc_id = "{{ variables.ops_vpc_id }}"
{% if variables.eks_version %}
eks-version = "{{ variables.eks_version }}"
{% endif %}
