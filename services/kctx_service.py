from libs.kube_api import KctxApi


def get_kubernetes_context(logger, data):
    kctx, err = KctxApi(logger).get_kubernetes_context(data)
    if err == 0:
        return kctx
    else:
        return {"error": kctx}
