from libs.kube_api import KctxApi
from libs.vault_api import Vault


def create_kubernetes_context(logger, data):
    vault = Vault(logger)
    kctx_api = KctxApi(vault, logger)
    return kctx_api.save_kubernetes_context(data)


def get_kubernetes_context(logger, data):
    vault = Vault(logger)
    kctx_api = KctxApi(vault, logger)
    kctx, err = kctx_api.get_kubernetes_context(data)
    return kctx


def delete_kubernetes_context(logger, data):
    vault = Vault(logger)
    kctx_api = KctxApi(vault, logger)
    return kctx_api.delete_kubernetes_context(data)
