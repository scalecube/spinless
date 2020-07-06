import os
import time
from datetime import datetime

from common.kube_api import KctxApi
from common.vault_api import Vault
from helm.helm_api import HelmDeployment
from helm.registry_api import RegistryApi
from helm.helm_processor import JobAndDeployment

dev_mode = os.getenv("DEV_MODE", False)


class HelmService:

    def __init__(self, helm_results, helm_processor):
        # 10 charts - 1 min for each, plus wait time in case of same namespace parallel installation
        self.TIMEOUT_MIN = 20.
        self.helm_results = helm_results
        self.helm_processor = helm_processor

    def _await_helms_installation(self, job_id, expected_services_count):
        """
        Await for job completion and return status
        :param job_id: job id
        :param expected_services_count: expected number of services to await for completion
        :return:
        """
        end_waiting = datetime.now().timestamp() + self.TIMEOUT_MIN * 60 * 1000
        curr_status = self.helm_results.get(job_id)
        while datetime.now().timestamp() <= end_waiting:
            curr_status = self.helm_results.get(job_id, {"services": []})
            if expected_services_count != len(curr_status["services"]):
                time.sleep(1.)
            else:
                self.helm_results.pop(job_id)
                return curr_status
        self.helm_results.pop(job_id)
        return curr_status

    def helm_deploy(self, job_ref, app_logger):
        if self.helm_results is None or self.helm_processor is None:
            return job_ref.complete_err(
                "Spinless is not initialized properly and can't work with helms. Check Helm task queue initialization")
        try:
            data = job_ref.data
            job_ref.emit("RUNNING", f'Start service deploy to kubernetes namespace: {data.get("namespace")}')

            # Common params
            common_props, code = self.__common_params(data)
            if code != 0:
                return job_ref.complete_err(common_props)

            # Params for helms
            registry_api = RegistryApi(app_logger)
            kctx_api = KctxApi(app_logger)
            services = []
            # TODO: read kubernetes config once per cluster and store in map
            for service in data.get("services", []):
                dependency, code = self.__helm_params(service, registry_api, kctx_api, job_ref, common_props['env'])
                if code != 0:
                    return job_ref.complete_err(dependency)
                services.append(dependency)

            # Install services
            job_ref.emit("RUNNING", f'Installing {len(services)} charts into namespace {common_props["namespace"]}')
            for service in services:
                self.__install_single_helm(job_ref, app_logger, common_props, service)
            status = self._await_helms_installation(job_ref.job_id, len(services))
            for result in status.get("services", []):
                job_ref.emit_all("RUNNING", result.get("log", ()))
            errors = list(filter(lambda s: s.get("error_code", 1) != 0, status.get("services")))
            if len(errors) == 0 and len(status.get("services")) == len(services):
                job_ref.complete_succ(f'Installed {len(services)}/{len(services)} services')
            else:
                job_ref.complete_err(
                    f'Installed {len(status.get("services")) - len(errors)} /{len(services)} services. With errors: {len(errors)}')
        except Exception as ex:
            job_ref.complete_err(f'Unexpected error while installing services,  reason: {ex}')

    def helm_destroy(self, job_ref, app_logger):
        data = job_ref.data
        clusters = data.get("clusters")
        namespace = data.get("namespace")
        services = data.get("services")
        try:
            job_ref.emit("RUNNING", f'Destroying environment: {namespace} in cluster {clusters}')
            # destroy namespace

            [KctxApi(app_logger).delete_ns(cluster_, namespace) for cluster_ in clusters]
            job_ref.emit("RUNNING", 'Deleted namespace from k8')

            for service in services:
                s, err = Vault(app_logger, owner=service.get("owner", ""),
                               repo=service.get("repo", "")).delete_service_path(namespace)
                if err != 0:
                    job_ref.emit("RUNNING", f"Failed to delete vault path: {s}")
            job_ref.complete_succ(f'Destroyed env {namespace} with {len(services)} services')
        except Exception as ex:
            job_ref.complete_err(f'Failed to destroy env {namespace}: {str(ex)}')

    def helm_list(self, data, app_logger):
        clusters = data.get("clusters")
        namespace = data.get("namespace")
        try:
            app_logger.info(f'Getting versions of services in ns={namespace}, clusters={clusters}')
            service_versions = []
            for cluster in clusters:
                res, code = KctxApi(app_logger).get_services_by_namespace(cluster, namespace)
                if code == 0:
                    service_versions.append({"cluster": cluster, "services": res})
                else:
                    app_logger.warn(res)
                    service_versions.append({"cluster": cluster, "services": []})
            return service_versions, 0
        except Exception as ex:
            app_logger.error(str(ex))
            return str(ex), 1

    # Private methods

    def __common_params(self, data):
        if not all(k in data for k in ("namespace", "sha")):
            return "Not all mandatory fields provided: \"namespace\", \"sha\"", 1
        result = {
            'namespace': data["namespace"],
            'sha': data["sha"],
            'env': data.get('env', {}),
            'base_namespace': data.get('base_namespace')
        }
        return result, 0

    def __helm_params(self, service, reg_api, kctx_api, job_ref, env):
        if not all(k in service for k in ("owner", "repo", "registry", "cluster")):
            return "owner/repo/registry/cluster are mandatory ", 1
        registries_fetched, err = self.__prepare_regs(service["registry"], reg_api)
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
        service['env'] = env.update(service.get("env", {}))
        return service, 0

    def __prepare_regs(self, registries, registry_api):
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

    def __install_single_helm(self, job_ref, app_logger, common_props, helm):
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
            self.helm_processor.submit_deployment(JobAndDeployment(job_ref.job_id, deployment))
        except Exception as ex:
            return str(ex), 1
