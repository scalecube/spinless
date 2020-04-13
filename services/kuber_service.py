from libs.cloud_provider_api import CloudApi
from libs.infrastructure import TF
from libs.kube_api import KctxApi
from libs.vault_api import Vault

DEFAULT_CLOUD = {"type": "eks", "name": "default"}


def kube_cluster_create(job_ref, app_logger):
    try:
        data = job_ref.data
        job_ref.emit("RUNNING: Start cluster creation job: {}".format(data.get("namespace")), None)

        # use vault later
        vault = Vault(logger=app_logger)

        cloud_provider_api = CloudApi(vault, app_logger)
        kctx_api = KctxApi(vault, app_logger)
        cloud_profile_req = data.get("cloud_profile", DEFAULT_CLOUD)
        cloud_profile = cloud_provider_api.get_cloud_provider(cloud_profile_req)
        cluster_name = data["cluster_name"]
        job_ref.emit("RUNNING: using cloud profile:{} to create cluster: {}".format(cloud_profile_req, cluster_name),
                     None)
        terraform = TF(app_logger, cloud_profile["aws_region"], cloud_profile["aws_access_key"],
                       cloud_profile["aws_secret_key"],
                       cluster_name, cloud_profile["az1"], cloud_profile["az2"], cloud_profile["kube_nodes_amount"],
                       data["kube_nodes_instance_type"], kctx_api)

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
