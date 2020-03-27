import logging

from libs.job_api import JobState
from libs.log_api import JobLogger
from libs.vault_api import Vault


def deploy(ctx):
    data = ctx.data
    logger = JobLogger(data['owner'], data['repo'], ctx.id)
    logger.emit(JobState.RUNNING.name, "starting deploying to kubernetes namespace: {}".format(data.get("namespace")))
    logger.emit(JobState.RUNNING.name, "starting deploy")
    try:
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

        logger.emit(JobState.SUCCESS.name, "deployed successfully")
    except Exception as e:
        logger.emit(JobState.FAILED.name, "failed to deploy")
        logger.end()

    else:
        logger.end()
