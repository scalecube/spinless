from libs.cloud_provider_api import CloudApi
from libs.vault_api import Vault

__SUPPORTED_TYPES = "eks"

def create_cloud_provider(logger, data):
    vault = Vault(logger)
    repo = CloudApi(vault, logger)
    if not __check_type(data.get("type")):
        return {"error": "type not supported: {}".format(type)}
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