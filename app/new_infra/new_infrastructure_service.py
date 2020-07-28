import base64

from common.kube_api import KctxApi
from common.shell import create_dirs, shell_run
from common.vault_api import Vault
from new_infra.new_terraform_api import Terraform


class InfrastructureService:

    def __init__(self, app_logger):
        self.app_logger = app_logger
        pass

    def __setup_git_ssh(self, common_vault_data):
        try:
            # write git ssh keys to disk
            create_dirs("/root/.ssh")
            with open("/root/.ssh/id_rsa", "w") as id_rsa:
                id_rsa_decoded = base64.standard_b64decode(common_vault_data['git_ssh_key']).decode("utf-8")
                id_rsa.write(id_rsa_decoded)
            with open("/root/.ssh/id_rsa.pub", "w") as id_rsa_pub:
                id_rsa_pub_decoded = base64.standard_b64decode(common_vault_data['git_ssh_key_pub']).decode("utf-8")
                id_rsa_pub.write(id_rsa_pub_decoded)
            shell_run('chmod 400 /root/.ssh/*')
            shell_run('eval "$(ssh-agent -s)"')
            shell_run('ssh-add /root/.ssh/id_rsa')

        except Exception as err:
            self.app_logger.error(f"Failed to write git keys from vault to disk: {str(err)}")

    def create_cluster(self, job_ref, app_logger):
        try:
            data = job_ref.data
            self.app_logger.info("Starting cluster creation...")
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

            job_ref.emit(f"RUNNING: Start cluster creation job: {data.get('cluster_name')}", None)

            #  Get secrets for secret_name
            vault = Vault(logger=self.app_logger)
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

            self.__setup_git_ssh(common_vault_data)
            secrets = vault.read(f"{cloud_secrets_path}/{data['secret_name']}")["data"]
            job_ref.emit(f"RUNNING: using cloud profile:{data} to create cluster", None)

            aws_creds = {"aws_region": data.get("region"),
                         "aws_access_key": secrets.get("aws_access_key"),
                         "aws_secret_key": secrets.get("aws_secret_key")}

            tf_vars = {
                "cluster_name": data.get("cluster_name"),
                "cluster_type": data.get("cluster_type"),
                "properties": data.get("properties"),
                "network_id": network_id,
                "nebula_cidr_block": nebula_cidr_block,
                "nebula_route_table_id": nebula_route_table_id,
                "peer_account_id": peer_account_id,
                "peer_vpc_id": peer_vpc_id}

            terraform = Terraform(self.app_logger,
                                  data.get("cluster_name"),
                                  aws_creds,
                                  tf_vars,
                                  dns_suffix=data.get("dns_suffix"),
                                  action="create")

            for (msg, res) in terraform.create_cluster():
                if res is None:
                    job_ref.emit("RUNNING", msg)
                else:
                    if res == 0:
                        job_ref.complete_succ(f'Finished. cluster created successfully')
                    else:
                        job_ref.complete_err(f'Finished. cluster creation failed: {msg}')
                    # Don't go further in job. it's over. if that failed, it will not continue the flow.
                    break

        except Exception as ex:
            job_ref.complete_err(f'failed to create cluster. reason {ex}')

    def destroy_cluster(self, job_ref, app_logger):
        try:
            data = job_ref.data
            kube_cluster_params = ("cluster_name",
                                   "region",
                                   "secret_name")

            # check mandatory params
            if not all(k in data for k in kube_cluster_params):
                return job_ref.complete_err(f'Not all mandatory params: {kube_cluster_params}')

            job_ref.emit(f"RUNNING: Start to destroy cluster: {data.get('cluster_name')}", None)

            #  Get secrets for secret_name
            vault = Vault(logger=self.app_logger)
            common_vault_data = vault.read(f"{vault.vault_secrets_path}/common")["data"]
            cloud_secrets_path = common_vault_data["cloud_secrets_path"]
            secrets = vault.read(f"{cloud_secrets_path}/{data['secret_name']}")["data"]
            job_ref.emit(f"RUNNING: using cloud profile:{data} to create cluster", None)

            aws_creds = {"aws_region": data.get("region"),
                         "aws_access_key": secrets.get("aws_access_key"),
                         "aws_secret_key": secrets.get("aws_secret_key")}

            terraform = Terraform(logger=self.app_logger,
                                  cluster_name=data.get("cluster_name"),
                                  aws_creds=aws_creds,
                                  action="destroy")

            for (msg, res) in terraform.destroy_cluster():
                if res is None:
                    job_ref.emit("RUNNING", msg)
                else:
                    if res == 0:
                        job_ref.complete_succ(f'Finished. cluster deleted successfully')
                    else:
                        job_ref.complete_err(f'Finished. cluster deletion failed: {msg}')
                    break

        except Exception as ex:
            job_ref.complete_err(f'failed to delete cluster. reason {ex}')

    def list_clusters(self):
        return KctxApi(self.app_logger).get_clusters_list()

    def get_namespaces(self, cluster_name):
        nss, code = KctxApi(self.app_logger).get_ns(cluster_name)
        if code != 0:
            return {"error": nss}
        return {"result": nss}

    def delete_namespace(self, cluster_name, ns):
        nss, code = KctxApi(self.app_logger).delete_ns(cluster_name, ns)
        if code != 0:
            return {"error": nss}
        return {"result": nss}

    def create_cloud_secret(self, logger, secret_name, aws_access_key, aws_secret_key):
        vault = Vault(logger)
        common_data = vault.read(f"{vault.vault_secrets_path}/common")
        cloud_secrets_path = common_data["data"]["cloud_secrets_path"]
        vault.write(f"{cloud_secrets_path}/{secret_name}",
                    aws_access_key=aws_access_key,
                    aws_secret_key=aws_secret_key)
        return {f"Secret {secret_name}": "added"}
