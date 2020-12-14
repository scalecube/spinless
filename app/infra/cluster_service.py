import base64
import json

from jinja2 import Environment, FileSystemLoader


def resource_post_setup(terraform):
    # Apply node auth configmap
    yield "RUNNING: Applying node auth configmap...", None
    auth_conf_map_result, msg = terraform.apply_node_auth_configmap(kube_env)
    if auth_conf_map_result != 0:
        yield "FAILED: Failed to apply node config map...", auth_conf_map_result
    else:
        yield "SUCCESS: Cluster creation and conf setup complete", None
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
