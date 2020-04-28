import base64

from jinja2 import Environment, FileSystemLoader

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
                       cluster_name, cloud_profile.get("az1"),
                       cloud_profile.get("az2"),
                       cloud_profile.get("kube_nodes_amount"),
                       cloud_profile.get("kube_nodes_instance_type"),
                       kctx_api,
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
        job_ref.emit("ERROR", "failed to deploy reason {}".format(ex))
        job_ref.complete_err()


def post_cluster_operations(job_ref, app_logger):
    try:
        data = job_ref.data
        vault = Vault(logger=app_logger)

        with open("/tmp/conf-tmp", "w") as kube_conf:
            j2_env = Environment(loader=FileSystemLoader("templates"),
                                 trim_blocks=True)
            gen_template = j2_env.get_template('tmp.j2').render()
            kube_conf.write(gen_template)

        kube_conf_base64 = base64.standard_b64encode(gen_template.encode("utf-8")).decode("utf-8")
        vault.write("secretv2/tmp", **{"conf": kube_conf_base64})
        result_b64 = vault.read("secretv2/tmp")["data"]["conf"]

        app_logger.info("RESULT b64:{}".format(result_b64))
    except Exception as e:
        app_logger.error(str(e))
