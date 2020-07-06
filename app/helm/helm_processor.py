from multiprocessing import Process
from threading import Thread


class HelmProcessor:
    def __init__(self, task_queue, completion_dict):
        self.task_queue = task_queue
        self.completion_dict = completion_dict
        self.reader_thread = Thread(target=self._poll_queue)

    def start(self):
        self.reader_thread.start()
        return self

    def submit_deployment(self, job_and_deployment):
        print("Submitting task")
        self.task_queue.put(job_and_deployment)

    def _poll_queue(self):
        while True:
            print("Waiting for next task")
            job_and_deployment = self.task_queue.get()
            print("New task has arrived")
            deployment = job_and_deployment.deployment
            service_key = f'{deployment.namespace}/{deployment.owner}-{deployment.repo}'
            helm_result = {"service": service_key, "success": False}
            try:
                for (msg, code) in job_and_deployment.deployment.install_package():
                    if code is not None:
                        helm_result["success"] = code == 0
            except Exception as ex:
                helm_result["error"] = str(ex)

            # Report job status to shared memory map. It's up to consumer to keep track of it's size
            job_id = job_and_deployment.job_id
            current_services = self.completion_dict.get(job_id, {"services": []}).get("services")
            self.completion_dict[job_id] = {"services": current_services + [helm_result]}


class JobAndDeployment:
    def __init__(self, job_id, deployment):
        self.job_id = job_id
        self.deployment = deployment