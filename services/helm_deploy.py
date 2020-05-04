from libs.helm_api import HelmDeployment
from libs.kube_api import KctxApi
from libs.registry_api import RegistryApi
from libs.vault_api import Vault


def __common_params(data):
    if not all(k in data for k in ("owner", "branch", "namespace")):
        return "Not all mandatory fields provided: \"owner\", \"branch\", \"namespace\"", 1
    result = {
        'owner': data.get("owner", "no_owner"),
        'branch': data.get("branch", "no_branch"),
        'version': data.get("version", data.get("branch")),
        'environment_tags': data.get("environment_tags", data.get("branch")),
        'namespace': data.get("namespace", "no_namespace"),
        'sha': data.get("sha", "no_sha"),
        'issue_number': data.get("issue_number", "no_issue_number")
    }
    return result, 0


def __helms_params(data, common_regs, reg_api):
    result = []
    if "helm_charts" in data:
        # parse group of helms
        for h in data["helm_charts"]:
            helm_item = {}
            repo = h.get("repo")
            if not repo:
                return "repo name not provided for one of helms but \'helm_charts\' is present in request", 1
            helm_item["repo"] = repo
            # merge existing regs with ones overridden in helm
            regs_per_helm, err = __prepare_regs(h.get("registry", {}), reg_api)
            if err != 0:
                return regs_per_helm, err
            merged_reg = {**common_regs, **regs_per_helm}
            helm_item["registry"] = merged_reg
            helm_item["version"] = h.get("version", "0.0.1")
            result.append(helm_item)
    else:
        helm_item = {"registry": common_regs, "repo": data.get("repo", "no_repo"),
                     "version": data.get("helm", {}).get("version", "0.0.1")}
        result.append(helm_item)
    return result, 0


def __prepare_regs(registries, registry_api):
    """
    Get registries from vault. None will cause errer. pass empty dict if empty result expected. No defaults
    :param registries: reg_type -> reg_name mapping. Empty if no data
    :param registry_api: initialized registry api
    :return: reg_type -> reg_data from vault if the reg type to reg name exists. No defaults
    """
    result = {}
    for reg in registries:
        code, res = registry_api.get_reg({"type": reg, "name": registries.get(reg)})
        if code != 0:
            return res, code
        result[reg] = res
    return result, 0


def helm_deploy(job_ref, app_logger):
    try:
        ##
        # common params
        ##
        data = job_ref.data
        job_ref.emit("RUNNING", f'Start helm deploy to kubernetes namespace: {data.get("namespace")}')
        common_props, code = __common_params(data)
        if code != 0:
            return job_ref.complete_err(common_props)
        registry_api = RegistryApi(app_logger)
        common_registries, code = __prepare_regs(data.get("registry", {}), registry_api)
        if code != 0:
            return job_ref.complete_err(f'Failed to get registries data: {common_registries}')
        kctx_api = KctxApi(app_logger)
        # read cluster config
        cluster_name = data.get("kubernetes", {'cluster_name': 'default'}).get("cluster_name")
        k8s_cluster_conf, code = kctx_api.get_kubernetes_context(cluster_name)
        if code != 0:
            job_ref.emit("WARNING",
                         "Failed to get k8 conf for {}. Reason: {}. Will use default kube context for current vm".format(
                             cluster_name, k8s_cluster_conf))
            k8s_cluster_conf = {}

        ##
        # params per helm
        ##
        helm_params, code = __helms_params(data, common_registries, registry_api)
        if code != 0:
            return job_ref.complete_err(helm_params)

        for helm in helm_params:
            vault = Vault(logger=app_logger,
                          owner=common_props["owner"],
                          repo=helm["repo"],
                          branch=common_props["branch"])
            # Create role
            service_role, err_code = vault.create_role(cluster_name)
            deployment = HelmDeployment(
                logger=app_logger,
                owner=common_props.get("owner"),
                repo=helm.get("repo"),
                branch=common_props.get("branch"),
                helm_version=helm.get("version"),
                posted_values=common_props,
                registries=helm.get("registry"),
                k8s_cluster_conf=k8s_cluster_conf,
                namespace=common_props.get("namespace"),
                service_role=service_role,
                cluster_name=cluster_name
            )
            for (msg, code) in deployment.install_package():
                if code is None:
                    job_ref.emit("RUNNING", msg)
                else:
                    if code == 0:
                        job_ref.complete_succ('Helm deployed successfully')
                    else:
                        job_ref.complete_err(f'Helm deploy failed: {msg}')
                    break
    except Exception as ex:
        job_ref.complete_err(f'failed to deploy,  reason: {ex}')
