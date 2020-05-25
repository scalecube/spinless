from app.common.vault_api import Vault
from app.infra.cloud_provider_api import CloudApi

__SUPPORTED_TYPES = "eks"


def create_cloud_provider(logger, data):
    vault = Vault(logger)
    repo = CloudApi(vault, logger)
    if not __check_type(data.get("type")):
        return {"error": "type not supported: {}".format(data.get("type"))}
    return repo.save_cloud_provider(data)


def get_cloud_provider(logger, data):
    vault = Vault(logger)
    repo = CloudApi(vault, logger)
    result = repo.get_cloud_provider(data)
    return result


def delete_cloud_provider(logger, type, name):
    vault = Vault(logger)
    repo = CloudApi(vault, logger)
    return repo.delete_cloud_provider(type, name)


def __check_type(type):
    return type and type in __SUPPORTED_TYPES


def create_cloud_secret(logger, secret_name, aws_access_key, aws_secret_key):
    vault = Vault(logger)
    common_data = vault.read(f"{vault.vault_secrets_path}/common")
    cloud_secrets_path = common_data["data"]["cloud_secrets_path"]
    vault.write(f"{cloud_secrets_path}/{secret_name}",
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key)
    return {f"Secret {secret_name}": "added"}
