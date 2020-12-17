import base64
import json

from jinja2 import Environment, FileSystemLoader


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
