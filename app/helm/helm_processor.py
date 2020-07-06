from threading import Thread


class HelmProcessor:
    def __init__(self, task_queue, completion_dict, logger):
        self.task_queue = task_queue
        self.shared_completion_dict = completion_dict
        self.reader_thread = Thread(target=self._poll_queue)
        self.logger = logger

    def start(self):
        self.reader_thread.start()
        return self

    def submit_deployment(self, job_and_deployment):
        deployment = job_and_deployment.deployment
        self.logger.info(
            f"Submitting {job_and_deployment.job_id}, {deployment.namespace}/{deployment.owner}-{deployment.repo}")
        self.task_queue.put(job_and_deployment)

    def _poll_queue(self):
        while True:
            job_and_deployment = self.task_queue.get()
            deployment = job_and_deployment.deployment
            job_id = job_and_deployment.job_id
            service_key = f'{deployment.namespace}/{deployment.owner}-{deployment.repo}'
            self.logger.info(f"Job: {job_id}, Installing {service_key}")
            helm_result = {"service": service_key, "error_code": 1}
            try:
                err_code, output = job_and_deployment.deployment.install_package()
                helm_result["error_code"] = err_code
                helm_result["log"] = output
            except Exception as ex:
                helm_result["log"] = [str(ex)]

            # Report job status to shared memory map. It's up to consumer to keep track of it's size
            current_services = self.shared_completion_dict.get(job_id, {"services": []}).get("services")
            self.shared_completion_dict[job_id] = {"services": current_services + [helm_result]}


class JobAndDeployment:
    def __init__(self, job_id, deployment):
        self.job_id = job_id
        self.deployment = deployment
