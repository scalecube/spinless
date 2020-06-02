import os

from common.kube_api import KctxApi
from common.vault_api import Vault
from helm.helm_api import HelmDeployment
from helm.registry_api import RegistryApi

dev_mode = os.getenv("DEV_MODE", False)

def __common_params(data):
    if not all(k in data for k in ("namespace", "sha")):
        return "Not all mandatory fields provided: \"namespace\", \"sha\"", 1
    result = {
        'namespace': data["namespace"],
        'sha': data["sha"],
        'env': data.get('env', {}),
        'base_namespace': data.get('base_namespace')
    }
    return result, 0


def __helm_params(service, reg_api, kctx_api, job_ref):
    if not all(k in service for k in ("owner", "repo", "registry", "cluster")):
        return "owner/repo/registry/cluster are mandatory ", 1
    registries_fetched, err = __prepare_regs(service["registry"], reg_api)
    if err != 0:
        return registries_fetched, err
    service["registry"] = registries_fetched

    k8s_cluster_conf, code = kctx_api.get_kubernetes_context(service["cluster"])
    if code != 0:
        if dev_mode:
            job_ref.emit("INFO",
                         f'Failed to get k8 conf for {service["cluster"]}. Using local one')
            k8s_cluster_conf = {"cluster_name": service["cluster"]}
        else:
            return f'Failed to get k8 context for cluster {service["cluster"]}', 1
    service["k8s_cluster_conf"] = k8s_cluster_conf
    service["image_tag"] = service.get("image_tag")
    return service, 0


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
        data = job_ref.data
        job_ref.emit("RUNNING", f'Start service deploy to kubernetes namespace: {data.get("namespace")}')

        # Common params
        common_props, code = __common_params(data)
        if code != 0:
            return job_ref.complete_err(common_props)

        # Params for helms
        registry_api = RegistryApi(app_logger)
        kctx_api = KctxApi(app_logger)

        services = []
        for service in data.get("services", []):
            dependency, code = __helm_params(service, registry_api, kctx_api, job_ref)
            if code != 0:
                return job_ref.complete_err(dependency)
            services.append(dependency)

        # Install services
        installed_services = []
        failed_services = []
        job_ref.emit("RUNNING", f'Installing {len(services)} dependencies')
        for idx, service in enumerate(services, 1):
            job_ref.emit("RUNNING", f'Installing service[{idx}]: {service["repo"]}')
            msg, code = __install_single_helm(job_ref, app_logger, common_props, service)
            if code == 0:
                job_ref.emit("RUNNING", f'Service installed: {service["repo"]}')
                installed_services.append(service["repo"])
            else:
                job_ref.emit("RUNNING", f'Service installation failed: {service["repo"]} ({msg})')
                failed_services.append(service["repo"])
                # return job_ref.complete_err(f'Failed to install service {service["repo"]}. Reason: {msg}')

        # Finally, install target service
        service = data.get("service")
        if service:
            job_ref.emit("RUNNING", f'Installing service {service["repo"]}')
            target_service, code = __helm_params(service, registry_api, kctx_api, job_ref)
            if code != 0:
                return job_ref.complete_err(target_service)

            msg, code = __install_single_helm(job_ref, app_logger, common_props, target_service)
            if code != 0:
                failed_services.append(service["repo"])
                job_ref.emit("RUNNING", f'Service installation failed: {service["repo"]}')
                # return job_ref.complete_err(f'Failed to install service {target_service["repo"]}. Reason: {msg}')
            else:
                installed_services.append(service["repo"])
        job_ref.emit("RUNNING", f'Installed: {installed_services}')
        job_ref.emit("RUNNING", f'Failed to install: {failed_services}')
        if len(failed_services) > 0:
            return job_ref.complete_err(
                f'{len(installed_services)}/{len(installed_services) + len(failed_services)} services deployed, namespace={data["namespace"]}')
        else:
            return job_ref.complete_succ(
                f'{len(installed_services)}/{len(installed_services) + len(failed_services)} services deployed, namespace={data["namespace"]}')
    except Exception as ex:
        job_ref.complete_err(f'Unexpected failure while installing services,  reason: {ex}')


def __install_single_helm(job_ref, app_logger, common_props, helm):
    posted_values = {**common_props,
                     **{k: helm[k] for k in helm if k in ("owner", "repo", "image_tag")}}
    try:
        vault = Vault(logger=app_logger,
                      owner=helm["owner"],
                      repo=helm["repo"],
                      cluster_name=helm["cluster"])
        service_role, err_code = vault.create_role()
        vault.prepare_service_path(common_props.get("base_namespace"), common_props.get('namespace'))
        if err_code != 0:
            return f'Failed to create role: {service_role}', 1
        deployment = HelmDeployment(app_logger, helm["k8s_cluster_conf"], common_props["namespace"], posted_values,
                                    helm["owner"], helm["image_tag"], helm["repo"], helm["registry"], service_role,
                                    "0.0.1")
        for (msg, code) in deployment.install_package():
            if code is None:
                job_ref.emit("RUNNING", msg)
            else:
                return msg, code
    except Exception as ex:
        return str(ex), 1
