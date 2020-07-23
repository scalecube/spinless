from common.kube_api import KctxApi
from common.vault_api import Vault
from infra.terraform_api import Terraform


def create_cluster(job_ref, app_logger):
    try:
        data = job_ref.data
        app_logger.info("Starting cluster creation...")

        kube_cluster_params = ("cluster_name",
                               "cluster_type",
                               "region",
                               "cloud",
                               "secret_name",
                               "dns_suffix",
                               "properties")

        # check mandatory params
        if not all(k in data for k in kube_cluster_params):
            return job_ref.complete_err(f'Not all mandatory params: {kube_cluster_params}')

        job_ref.emit("RUNNING: Start cluster creation job: {}".format(data.get("namespace")), None)

        #  Get secrets for secret_name
        vault = Vault(logger=app_logger)
        common_path = f"{vault.vault_secrets_path}/common"

        # Get network_id (for second octet),
        # increase number for new cluster,
        # save for next deployments
        #
        common_vault_data = vault.read(common_path)["data"]
        cloud_secrets_path = common_vault_data["cloud_secrets_path"]
        network_id = int(common_vault_data["network_id"]) + 1
        common_vault_data.update({"network_id": str(network_id)})
        nebula_cidr_block = common_vault_data["nebula_cidr_block"]
        nebula_route_table_id = common_vault_data["nebula_route_table_id"]
        peer_account_id = common_vault_data["peer_account_id"]
        peer_vpc_id = common_vault_data["peer_vpc_id"]
        vault.write(common_path, **common_vault_data)

        secrets = vault.read(f"{cloud_secrets_path}/{data['secret_name']}")["data"]

        job_ref.emit(f"RUNNING: using cloud profile:{data} to create cluster", None)

        terraform = Terraform(logger=app_logger,
                              aws_region=data.get("region"),
                              aws_access_key=secrets.get("aws_access_key"),
                              aws_secret_key=secrets.get("aws_secret_key"),
                              cluster_name=data.get("cluster_name"),
                              cluster_type=data.get("cluster_type"),
                              kctx_api=KctxApi(app_logger),
                              properties=data.get("properties"),
                              dns_suffix=data.get("dns_suffix"),
                              network_id=network_id,
                              nebula_cidr_block=nebula_cidr_block,
                              nebula_route_table_id=nebula_route_table_id,
                              peer_account_id=peer_account_id,
                              peer_vpc_id=peer_vpc_id
                              )

        for (msg, res) in terraform.create_cluster():
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


def destroy_cluster(job_ref, app_logger):
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

        #  Get secrets for secret_name
        vault = Vault(logger=app_logger)
        cloud_secrets_path = vault.read(f"{vault.vault_secrets_path}/common")["data"]["cloud_secrets_path"]
        secrets = vault.read(f"{cloud_secrets_path}/{data['secret_name']}")["data"]

        job_ref.emit(f"RUNNING: using cloud profile:{data} to create cluster", None)
        terraform = Terraform(logger=app_logger,
                              aws_region=data.get("region"),
                              aws_access_key=secrets.get("aws_access_key"),
                              aws_secret_key=secrets.get("aws_secret_key"),
                              cluster_name=data.get("cluster_name"),
                              kctx_api=KctxApi(app_logger),
                              properties=data.get("properties"),
                              dns_suffix=data.get("dns_suffix"))

        for (msg, res) in terraform.destroy_cluster():
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


def list_clusters(logger):
    return KctxApi(logger).get_clusters_list()


def get_namespaces(cluster_name, app_logger):
    nss, code = KctxApi(app_logger).get_ns(cluster_name)
    if code != 0:
        return {"error": nss}
    return {"result": nss}


def delete_namespace(cluster_name, ns, app_logger):
    nss, code = KctxApi(app_logger).delete_ns(cluster_name, ns)
    if code != 0:
        return {"error": nss}
    return {"result": nss}


def create_cloud_secret(logger, secret_name, aws_access_key, aws_secret_key):
    vault = Vault(logger)
    common_data = vault.read(f"{vault.vault_secrets_path}/common")
    cloud_secrets_path = common_data["data"]["cloud_secrets_path"]
    vault.write(f"{cloud_secrets_path}/{secret_name}",
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key)
    return {f"Secret {secret_name}": "added"}
