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
            return job_ref.complete_err(f'Not all mandatory params: {["cloud_profile", "cluster_name", "dns_suffix"]}')

        cloud_provider_api = CloudApi(vault, app_logger)
        kctx_api = KctxApi(app_logger)
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
                       cloud_profile.get("nodePools"),
                       dns_suffix)

        for (msg, res) in terraform.install_kube():
            if res is None:
                job_ref.emit("RUNNING", msg)
            else:
                if res == 0:
                    job_ref.complete_succ(f'Finished. cluster created successfully: {msg}')
                else:
                    job_ref.complete_err(f'Finished. cluster creation failed: {msg}')
                # Don't go further in job. it's over. if that failed, it will not continue the flow.
                break

    except Exception as ex:
        job_ref.complete_err(f'failed to create cluster. reason {ex}')


def kube_cluster_delete(job_ref, app_logger):
    try:
        data = job_ref.data
        # check mandatory params
        if "cluster_name" not in data:
            return job_ref.complete_err('Not all mandatory params: \"cluster_name\"')

        cluster_name = data.get("cluster_name")
        app_logger.info("Starting cluster removal for {}...".format(cluster_name))

        # use vault later
        kctx_api = KctxApi(app_logger)
        cluster_ctx, err = kctx_api.get_kubernetes_context(cluster_name)
        if err != 0:
            return job_ref.complete_err(f'Cluster does not exist: {cluster_name}')

        terraform = TF(app_logger,
                       cluster_ctx["aws_region"],
                       cluster_ctx["aws_access_key"],
                       cluster_ctx["aws_secret_key"],
                       cluster_name,
                       kctx_api,
                       kube_conf=cluster_ctx["kube_config"])

        for (msg, res) in terraform.delete_kube():
            if res is None:
                job_ref.emit("RUNNING", msg)
            else:
                if res == 0:
                    job_ref.complete_succ(f'Finished. cluster removal complete: {msg}')
                else:
                    job_ref.complete_err(f'Finished. cluster removal failed: {msg}')
                # Don't go further in job. it's over. if that failed, it will not continue the flow.
                break

    except Exception as ex:
        job_ref.complete_err(f'failed to delete cluster {ex}')


def get_ns(cluster_name, app_logger):
    nss, code = KctxApi(app_logger).get_ns(cluster_name)
    if code != 0:
        return {"error": nss}
    return {"result": nss}


def delete_ns(cluster_name, ns, app_logger):
    nss, code = KctxApi(app_logger).delete_ns(cluster_name, ns)
    if code != 0:
        return {"error": nss}
    return {"result": nss}
