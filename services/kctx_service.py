from libs.kube_api import KctxApi


def list_clusters(logger):
    return KctxApi(logger).get_clusters_list()
