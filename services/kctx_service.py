from libs.kube_api import KctxApi
from libs.vault_api import Vault

def get_kubernetes_context(logger, data):
    vault = Vault(logger)
    kctx_api = KctxApi(vault, logger)
    err, kctx = kctx_api.get_kubernetes_context(data)
    return kctx
