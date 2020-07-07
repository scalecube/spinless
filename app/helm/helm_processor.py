from threading import Thread

from common.vault_api import Vault
from helm.helm_api import HelmDeployment


class HelmProcessor:
    def __init__(self, task_queue, completion_dict, logger):
        self.task_queue = task_queue
        self.shared_completion_dict = completion_dict
        self.reader_thread = Thread(target=self._poll_queue)
        self.logger = logger

    def start(self):
        self.reader_thread.start()
        return self

    def submit_deployment(self, helm_task):
        values = helm_task.helm_values
        key = f'{values["namespace"]}/{values["owner"]}-{values["repo"]}'
        self.logger.info(f"Submitting {helm_task.job_id}, {key}")
        self.task_queue.put(helm_task)

    def _poll_queue(self):
        while True:
            helm_task = self.task_queue.get()
            job_id = helm_task.job_id

            # actually install helm release
            helm_result = self.__process_single_deployment(helm_task)

            # Report job status to shared memory map. It's up to consumer to keep track of it's size
            current_services = self.shared_completion_dict.get(job_id, {"services": []}).get("services")
            # Write access is single threaded so it's safe operation
            self.shared_completion_dict[job_id] = {"services": current_services + [helm_result]}

    def __process_single_deployment(self, helm_task):
        values = helm_task.helm_values
        service_key = f'{values["namespace"]}/{values["owner"]}-{values["repo"]}'
        self.logger.info(f"Job: {helm_task.job_id}, Installing {service_key}")
        helm_result = {"service": service_key, "error_code": 1}
        try:
            vault = Vault(self.logger, values['owner'], values['repo'], values['cluster'])
            service_role, err_code = vault.create_role()
            if err_code != 0:
                helm_result["log"] = f'Failed to create role: {service_role}'
                return helm_result

            vault.prepare_service_path(values.get('base_namespace'), values.get('namespace'))
            helm_deployment = HelmDeployment(self.logger, values, helm_task.k8_config, helm_task.registry)
            err_code, output = helm_deployment.install_package()
            helm_result["error_code"] = err_code
            helm_result["log"] = output
        except Exception as ex:
            helm_result["log"] = [str(ex)]
        return helm_result


class HelmTask:
    def __init__(self, job_id, helm_values, registry, k8_config):
        self.job_id = job_id
        self.helm_values = helm_values
        self.registry = registry
        self.k8_config = k8_config
