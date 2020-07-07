import os
import time
from datetime import datetime

from common.kube_api import KctxApi
from common.vault_api import Vault
from helm.helm_api import HelmDeployment
from helm.helm_processor import HelmTask
from helm.registry_api import RegistryApi

dev_mode = os.getenv("DEV_MODE", False)
SUPPORTED_HELM_PROPERTIES = ("owner", "repo", "image_tag", "env", "namespace", "base_namespace", "cluster")


class HelmService:

    def __init__(self, helm_results, helm_processor):
        # 10 charts - 1 min for each, plus wait time in case of same namespace parallel installation
        self.TIMEOUT_MIN = 20.
        self.helm_results = helm_results
        self.helm_processor = helm_processor

    def __await_helms_installation(self, job_id, expected_services_count):
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
            helms_input = data.get("services", [])
            job_ref.emit("RUNNING", f'Start deployment of {len(helms_input)} services')

            # Check mandatory params:
            mandatory_params = ("owner", "repo", "registry", "cluster", "namespace", "image_tag")
            for h in helms_input:
                if not all(k in h for k in mandatory_params):
                    return job_ref.complete_err(f"Not all mandatory params ({mandatory_params}) "
                                                f"provided for chart {h.get('repo', 'undefined')}.")

            # Parse k8 Contexts and registries for all services for helms
            registries, err = self.__parse_registries(app_logger, helms_input)
            if err != 0:
                return job_ref.complete_err(registries)
            k8_contexts, err = self.__parse_k8_contexts(app_logger, helms_input)
            if err != 0:
                return job_ref.complete_err(k8_contexts)

            job_ref.emit("RUNNING", f'Installing {len(helms_input)} helm releases...')
            for h_input in helms_input:
                helm_properties = {k: v for (k, v) in h_input.items() if k in SUPPORTED_HELM_PROPERTIES}
                registry = {r_type: registries.get(r_type).get(r_name) for (r_type, r_name) in
                            h_input["registry"].items()}
                k8_config = k8_contexts.get(h_input["cluster"])

                helm_task = HelmTask(job_ref.job_id, helm_properties, registry, k8_config)
                # Submit tasks to install services
                self.helm_processor.submit_deployment(helm_task)

            # Await for the tasks to complete
            status = self.__await_helms_installation(job_ref.job_id, len(helms_input))
            for result in status.get("services", []):
                job_ref.emit_all("RUNNING", result.get("log", ()))
            errors = list(filter(lambda s: s.get("error_code", 1) != 0, status.get("services")))
            if len(errors) == 0 and len(status.get("services")) == len(helms_input):
                job_ref.complete_succ(f'Installed {len(helms_input)}/{len(helms_input)} services')
            else:
                job_ref.complete_err(
                    f'Installed {len(status.get("services")) - len(errors)} /{len(helms_input)} services. '
                    f'With errors: {len(errors)}')
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

    def __parse_k8_contexts(self, app_logger, helms_input):
        """
        map cluster -> k8 context for all clusters in request
        :param app_logger: logger
        :param helms_input: helm charts to install that were received in user request
        :return: (mapping, 0) in case of success, (err message, err_code) - otherwise
        """
        result = {}
        clusters = set(map(lambda h: h.get("cluster", ""), helms_input))
        k8_config_api = KctxApi(app_logger)
        for cluster in clusters:
            context, err = k8_config_api.get_kubernetes_context(cluster)
            if err != 0:
                return f"Failed to read context for cluster {cluster}", 1
            result[cluster] = context
        return result, 0

    def __parse_registries(self, app_logger, helms_input):
        registry_types = ("docker", "helm")
        result = {reg_type: {} for reg_type in registry_types}
        registry_api = RegistryApi(app_logger)
        for registry_type in registry_types:
            for registry_name in set(map(lambda h: h.get("registry", {}).get(registry_type, ""), helms_input)):
                registry, err = registry_api.get_registry(registry_type, registry_name)
                if err != 0:
                    return f"Failed to read {registry_type} registry {registry_name}", 1
                result[registry_type][registry_name] = registry
        return result, 0
