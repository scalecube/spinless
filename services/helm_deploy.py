from libs.helm_api import Helm
from libs.kube_api import KctxApi
from libs.registry_api import RegistryApi
from libs.vault_api import Vault


def create_posted_env(data):
    posted_env = {
        'OWNER': data.get("owner", "no_owner"),
        'REPO': data.get("repo", "no_repo"),
        'BRANCH_NAME': data.get("branch_name", "no_branch_name"),
        'SHA': data.get("sha", "no_sha"),
        'PR': data.get("issue_number", "no_issue_number"),
        'NAMESPACE': data.get("namespace", "no_namespace")
    }
    return posted_env


def __parse_reg_from_data(data, reg_type):
    """Return { "docker/helm", "name" : registry_name"};
        default registry name should be "default"
        """
    res = {"type": reg_type, "name": data.get("registry", {}).get(reg_type, "default")}
    return res


def __prepare_regs(data, registry_api):
    helm_reg = registry_api.get_reg(__parse_reg_from_data(data, "helm"))
    if "error" in helm_reg:
        return helm_reg
    docker_reg = registry_api.get_reg(__parse_reg_from_data(data, "docker"))
    registries = {"helm": helm_reg, "docker": docker_reg}
    return registries


def helm_deploy(job_ref, app_logger):
    try:
        data = job_ref.data
        job_ref.emit("RUNNING", "start helm deploy to kubernetes namespace: {}".format(data.get("namespace")))
        posted_env = create_posted_env(data)

        vault = Vault(logger=app_logger)
        registry_api = RegistryApi(vault, app_logger)
        kctx_api = KctxApi(vault, app_logger)

        job_ref.emit("RUNNING", "kctx_api: {}".format(kctx_api))
        job_ref.emit("RUNNING", "data: {}".format(data))

        # read cluster config
        kube_profile_req = data.get("kubernetes", {'cluster_name': 'default'}).get("cluster_name")
        k8s_cluster_conf = kctx_api.get_kubernetes_context(kube_profile_req)
        if "error" in k8s_cluster_conf:
            job_ref.emit("WARNING",
                         "Failed to get k8 conf for {}. Reason: {}. Will use default kube context for current vm".format(
                             kube_profile_req, k8s_cluster_conf.get("error")))
            k8s_cluster_conf = {}

        # read registries config
        registries = __prepare_regs(data, registry_api)
        if "error" in registries:
            job_ref.emit("ERROR", "Failed to get registries data for {}. Reason: {}".format(data.get("registry"),
                                                                                            registries.get("error")))
            job_ref.complete_err()
            return

        helm = Helm(
            logger=app_logger,
            owner=data.get("owner"),
            repo=data.get("repo"),
            branch_name=data.get("branch_name"),
            helm_version=data.get("helm_chart_version", "0.0.1"),
            posted_env=posted_env,
            registries=registries,
            k8s_cluster_conf=k8s_cluster_conf
        )
        for (msg, res) in helm.install_package():
            if not res:
                job_ref.emit("RUNNING", msg)
            else:
                if res.code == 0:
                    job_ref.emit("SUCCESS", "finished. helm deployed successfully: {}".format(res.stdout))
                    job_ref.complete_succ()
                else:
                    job_ref.emit("ERROR", "finished. helm deployed failed: {}".format(res.stdout))
                    job_ref.complete_err()
                # Don't go further in job. it's over. if that failed, it will not continue the flow.
                break

    except Exception as ex:
        job_ref.emit("ERROR", "failed to deploy reason {}".format(ex))
        job_ref.complete_err()
