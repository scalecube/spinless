from libs.cloud_provider_api import CloudApi
from libs.vault_api import Vault


def create_cloud_provider(logger, data):
    vault = Vault(logger)
    repo = CloudApi(vault, logger)
    return repo.save_cloud_provider(data)


def get_cloud_provider(logger, data):
    vault = Vault(logger)
    repo = CloudApi(vault, logger)
    result = repo.get_cloud_provider(data)
    return result


def delete_cloud_provider(logger, data):
    vault = Vault(logger)
    repo = CloudApi(vault, logger)
    return repo.delete_cloud_provider(data)
