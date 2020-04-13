from libs.cloud_provider_api import CloudApi
from libs.infrastructure import TF
from libs.vault_api import Vault


def kube_cluster_create(job_ref, applogger):
    try:
        data = job_ref.data
        job_ref.emit("RUNNING: Start cluster creation job: {}".format(data.get("namespace")), None)

        # use vault later
        vault = Vault(logger=applogger)
        cloud_provider_api = CloudApi(vault, applogger)
        terraform = TF(applogger, data["aws_region"], data["aws_access_key"], data["aws_secret_key"],
                       data["cluster_name"], data["az1"], data["az2"], data["kube_nodes_amount"],
                       data["kube_nodes_instance_type"])

        for (msg, res) in terraform.install_kube():
            if not res:
                job_ref.emit("RUNNING", msg)
            else:
                if res == 0:
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
