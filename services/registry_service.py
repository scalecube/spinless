from libs.registry_api import RegistryApi
from libs.vault_api import Vault


def create_registry(logger, data):
    vault = Vault(logger)
    reg_api = RegistryApi(vault, logger)
    return reg_api.save_reg(data)


def get_registry(logger, kctx_id):
    vault = Vault(logger)
    reg_api = RegistryApi(vault, logger)
    reg = reg_api.get_reg(kctx_id)
    if "error" not in reg:
        del reg["password"]
    return reg


def delete_registry(logger, kctx_id):
    vault = Vault(logger)
    reg_api = RegistryApi(vault, logger)
    return reg_api.delete_reg(kctx_id)
