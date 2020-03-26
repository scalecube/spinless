import logging

from libs.log_api import JobLogger
from libs.vault_api import Vault

ERROR = "ERROR"
SUCCESS = "SUCCESS"
RUNNING = "RUNNING"


def deploy(ctx):
    data = ctx.data
    logger = JobLogger(data['owner'], data['repo'], ctx.id)
    logger.info("starting deploying to kubernetes namespace: {}".format(data.get("namespace")))
    return
    vault = Vault(logger=logger,
                  root_path="secretv2",
                  vault_server=ctx.config["VAULT_ADDR"],
                  service_role=ctx.config["VAULT_ROLE"],
                  owner=data.get("owner"),
                  repo=data.get("repo"),
                  version=data.get("version"),
                  vault_secrets_path=ctx.config["VAULT_SECRETS_PATH"])
    service_account = vault.app_path
    spinless_app_env = vault.get_self_app_env()
    vault.create_role()
    env = vault.get_env("env")
    # TODO: add env to helm and install
