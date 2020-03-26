from libs.vault_api import Vault

ERROR = "ERROR"
SUCCESS = "SUCCESS"
RUNNING = "RUNNING"


def deploy(app, ctx, data):
    try:
        ctx.update_status(RUNNING, "starting deploying to kubernetes namespace: {}".format(data.get("namespace")))
        vault = Vault(logger=app.logger,
                      root_path="secretv2",
                      vault_server=app.config["VAULT_ADDR"],
                      service_role=app.config["VAULT_ROLE"],
                      owner=data.get("owner"),
                      repo_slug=data.get("repo"),
                      version=data.get("version"),
                      vault_secrets_path=app.config["VAULT_SECRETS_PATH"])
        service_account = vault.app_path
        spinless_app_env = vault.get_self_app_env()
        vault.create_role()
        env = vault.get_env("env")
        # TODO: add env to helm and install
    except OSError:
        ctx.update_status(ERROR, "failed to deploy {}".format(data.get("namespace")))
        ctx.end()
    else:
        ctx.update_status(SUCCESS, "completed successfully the deployment of {}".format(data.get("namespace")))
        ctx.end()
