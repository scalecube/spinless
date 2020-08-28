import base64
import json

from jinja2 import Environment, FileSystemLoader

from common.kube_api import KctxApi
from common.vault_api import Vault

RESERVED_CLUSTERS = {"nebula", "uat-exchange", "uat-ops"}
CLUSTERS_COMMON_PATH = "secretv2/scalecube/spinless/resources/cluster/common"
INFRA_TEMPLATES_ROOT = "infra/templates"
RESOURCE_CLUSTER = 'cluster'


def compute_properties(logger):
    vault = Vault(logger)
    clusters_common_data = vault.read(CLUSTERS_COMMON_PATH)["data"]

    # Get network_id (for second octet), increase number for new cluster, save for next deployments
    network_id = int(clusters_common_data["network_id"]) + 1
    clusters_common_data.update({"network_id": str(network_id)})
    nebula_cidr_block = clusters_common_data["nebula_cidr_block"]
    nebula_route_table_id = clusters_common_data["nebula_route_table_id"]
    peer_account_id = clusters_common_data["peer_account_id"]
    peer_vpc_id = clusters_common_data["peer_vpc_id"]
    vault.write(CLUSTERS_COMMON_PATH, **clusters_common_data)

    common_cluster_properties = {
        "network_id": network_id,
        "nebula_cidr_block": nebula_cidr_block,
        "nebula_route_table_id": nebula_route_table_id,
        "peer_account_id": peer_account_id,
        "peer_vpc_id": peer_vpc_id
    }
    return common_cluster_properties


def props_to_tfvars(base_path, account, resource_name, properties=None):
    """
    Generate pair of secret and resource-related tfvar files. Writes to file and returns path-s
    In generated files, the content is strongly coupled with terraform code that consumes the files.
    The files are in fact passed as '-var-file' parameters
    :return aws_vars_path - path to secret tfvars file
            resource_vars_path - path to resource specific vars
            keys - list of all var names in first and second path-s
    """
    keys = []
    aws_vars_path = f"{base_path}/aws.tfvars"
    with open(aws_vars_path, "w") as aws_vars:
        aws_vars.write(f'aws_region = "{account["aws_region"]}"\n')
        aws_vars.write(f'aws_access_key = "{account["aws_access_key"]}"\n')
        aws_vars.write(f'aws_secret_key = "{account["aws_secret_key"]}"\n')
    keys.extend(["aws_region", "aws_access_key", "aws_secret_key"])

    resource_vars_path = None
    if properties:
        resource_vars_path = f"{base_path}/resource.tfvars"
        vars = properties
        vars["nodePools"] = json.dumps(vars["nodePools"])
        vars["resource_name"] = resource_name
        templates = Environment(loader=FileSystemLoader("infra/templates"), trim_blocks=True)
        with open(resource_vars_path, "w") as tfvars:
            gen_template = templates.get_template('template_tfvars.tf').render(variables=vars)
            tfvars.write(gen_template)
        # customize vard to match exactly variable names since they are to be present in main.ft as module args
        vars.pop("dns_suffix")
        vars.pop("resource_name")
        vars["cluster-name"] = resource_name
        keys.extend(list(vars.keys()))
    return aws_vars_path, resource_vars_path, keys


def resource_post_setup(terraform):
    # Generate cluster config
    yield "RUNNING: Generating kubernetes cluster config...", None
    kube_conf_str, err = KctxApi.generate_aws_kube_config(cluster_name=terraform.resource_name,
                                                          aws_region=terraform.account["aws_region"],
                                                          aws_access_key=terraform.account["aws_access_key"],
                                                          aws_secret_key=terraform.account["aws_secret_key"],
                                                          conf_path=terraform.kube_config_file_path,
                                                          templates_root=INFRA_TEMPLATES_ROOT
                                                          )
    if err == 0:
        yield "RUNNING: Kubernetes config generated successfully", None
    else:
        yield "ERROR: Failed to create kubernetes config", err

    kube_env = {"KUBECONFIG": terraform.kube_config_file_path,
                "AWS_DEFAULT_REGION": terraform.account["aws_region"],
                "AWS_ACCESS_KEY_ID": terraform.account["aws_access_key"],
                "AWS_SECRET_ACCESS_KEY": terraform.account["aws_secret_key"]
                }
    # Apply node auth configmap
    yield "RUNNING: Applying node auth configmap...", None
    auth_conf_map_result, msg = terraform.__apply_node_auth_configmap(kube_env)
    if auth_conf_map_result != 0:
        yield "FAILED: Failed to apply node config map...", auth_conf_map_result
    else:
        yield "SUCCESS: Cluster creation and conf setup complete", None

    # Provision Vault
    vault_prov_res, msg = terraform.kctx_api.provision_vault(terraform.resource_name, terraform.work_dir, kube_env,
                                                             templates_root=INFRA_TEMPLATES_ROOT)
    if vault_prov_res != 0:
        yield f"FAILED: Failed setup vault account in new cluster. Aborting: {msg}", vault_prov_res
    yield "Vault provisioning complete", None

    # Set up storage
    storage_res, msg = terraform.kctx_api.setup_storage(kube_env, terraform.work_dir,
                                                        templates_root=INFRA_TEMPLATES_ROOT)
    if storage_res != 0:
        yield "FAILED: Failed to setup storage volume. Aborting: {}".format(msg), storage_res
    yield "Storage volume set up successfully.", None

    #  Setup cluster autoscaler
    ca, msg = terraform.kctx_api.setup_ca(kube_env, terraform.resource_name, terraform.account["aws_region"])
    if ca != 0:
        yield "Failed to setup cluster autoscaler. Resuming anyway", None
    else:
        yield "Cluster autoscaler installed successfully.", None

    # Set up traefik
    traefik_res, msg = terraform.kctx_api.setup_traefik(kube_env)
    if traefik_res != 0:
        yield "Failed to setup traefik. Resuming anyway", None
    else:
        yield "Traefik installed successfully.", None

    # Set up metrics
    res, msg = terraform.kctx_api.setup_metrics(kube_env)
    if res != 0:
        yield f"FAILED: Failed to setup metrics. Aborting: {msg}", None
    yield "Metrics installed successfully.", None

    # If deployment was successful, save kubernetes context to vault
    kube_conf_base64 = base64.standard_b64encode(kube_conf_str.encode("utf-8")).decode("utf-8")
    terraform.kctx_api.save_aws_context(aws_access_key=terraform.account["aws_access_key"],
                                        aws_secret_key=terraform.account["aws_secret_key"],
                                        aws_region=terraform.account["aws_region"],
                                        kube_cfg_base64=kube_conf_base64,
                                        cluster_name=terraform.resource_name,
                                        dns_suffix=terraform.properties['dns_suffix'])
    yield "Saved cluster config.", None


def resource_post_destroy(terraform):
    # Generate cluster config
    yield "RUNNING: Performing cluster post-destroy actions...", None

    # Disable vault mount point
    res, msg = Vault(terraform.logger).disable_vault_mount_point(terraform.resource_name)
    if res != 0:
        yield f"FAILED: Failed to disable vault mount point", res
    yield f"Disabled Vault mount point for {terraform.resource_name}", None

    # If deployment was successful, save kubernetes context to vault
    terraform.kctx_api.delete_kubernetes_context(terraform.resource_name)
    yield "Cleared cluster config.", None
