from libs.cloud_provider_api import CloudApi
from libs.infrastructure import TF
from libs.kube_api import KctxApi
from libs.vault_api import Vault

DEFAULT_CLOUD = {"type": "eks", "name": "default"}


def kube_cluster_create(job_ref, app_logger):
    try:
        data = job_ref.data
        app_logger.info("Starting cluster creation...")
        job_ref.emit("RUNNING: Start cluster creation job: {}".format(data.get("namespace")), None)

        # use vault later
        vault = Vault(logger=app_logger)

        # check mandatory params
        if not all(k in data for k in ("cloud_profile", "cluster_name", "dns_suffix")):
            job_ref.emit("ERROR",
                         "Not all mandatory params: {}".format(["cloud_profile", "cluster_name", "dns_suffix"]))
            job_ref.complete_err()
            return

        cloud_provider_api = CloudApi(vault, app_logger)
        kctx_api = KctxApi(vault, app_logger)
        cloud_profile_req = data["cloud_profile"]
        cloud_profile = cloud_provider_api.get_cloud_provider(cloud_profile_req)
        cluster_name = data["cluster_name"]
        dns_suffix = data["dns_suffix"]
        job_ref.emit("RUNNING: using cloud profile:{} to create cluster: {}".format(cloud_profile_req, cluster_name),
                     None)

        terraform = TF(app_logger,
                       cloud_profile.get("aws_region"),
                       cloud_profile.get("aws_access_key"),
                       cloud_profile.get("aws_secret_key"),
                       cluster_name, kctx_api, cloud_profile.get("az1"),
                       cloud_profile.get("az2"),
                       cloud_profile.get("kube_nodes_amount"),
                       cloud_profile.get("kube_nodes_instance_type"),
                       dns_suffix)

        for (msg, res) in terraform.install_kube():
            if res is None:
                job_ref.emit("RUNNING", msg)
            else:
                if res == 0:
                    job_ref.emit("SUCCESS", "Finished. cluster created successfully:  {}".format(msg))
                    job_ref.complete_succ()
                else:
                    job_ref.emit("ERROR", "Finished. cluster creation failed: {}".format(msg))
                    job_ref.complete_err()
                # Don't go further in job. it's over. if that failed, it will not continue the flow.
                break

    except Exception as ex:
        job_ref.emit("ERROR", "failed to create cluster. reason {}".format(ex))
        job_ref.complete_err()


def kube_cluster_delete(job_ref, app_logger):
    try:
        data = job_ref.data
        # check mandatory params
        if "cluster_name" not in data:
            job_ref.emit("ERROR", "Not all mandatory params: {}".format("cluster_name"))
            job_ref.complete_err()
            return

        cluster_name = data.get("cluster_name")
        app_logger.info("Starting cluster removal for {}...".format(cluster_name))

        # use vault later
        vault = Vault(logger=app_logger)
        kctx_api = KctxApi(vault, app_logger)
        err, clsuter_ctx = kctx_api.get_kubernetes_context(cluster_name)
        if err != 0:
            job_ref.emit("ERROR", "Cluster does not exist: {}".format(cluster_name))
            job_ref.complete_err()
            return

        terraform = TF(app_logger,
                       clsuter_ctx["aws_region"],
                       clsuter_ctx["aws_access_key"],
                       clsuter_ctx["aws_secret_key"],
                       cluster_name,
                       kctx_api,
                       kube_conf=clsuter_ctx["kube_config"])

        for (msg, res) in terraform.delete_kube():
            if res is None:
                job_ref.emit("RUNNING", msg)
            else:
                if res == 0:
                    job_ref.emit("SUCCESS", "Finished. cluster removal complete: {}".format(msg))
                    job_ref.complete_succ()
                else:
                    job_ref.emit("ERROR", "Finished. cluster removal failed: {}".format(msg))
                    job_ref.complete_err()
                # Don't go further in job. it's over. if that failed, it will not continue the flow.
                break

    except Exception as ex:
        job_ref.emit("ERROR", "failed to delete cluster {}".format(ex))
        job_ref.complete_err()
