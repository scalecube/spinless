from libs.kube_api import KctxApi
from libs.vault_api import Vault


def create_kctx(logger, data):
    vault = Vault(logger)
    kctx_api = KctxApi(vault, logger)
    return kctx_api.save_k_ctx(data)


def get_kctx(logger, data):
    vault = Vault(logger)
    kctx_api = KctxApi(vault, logger)
    kctx = kctx_api.get_kctx(data)
    return kctx


def delete_kctx(logger, data):
    vault = Vault(logger)
    kctx_api = KctxApi(vault, logger)
    return kctx_api.delete_kctx(data)
