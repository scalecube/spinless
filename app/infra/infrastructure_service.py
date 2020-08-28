import base64
import os

from common.kube_api import KctxApi
from common.shell import create_dirs, shell_run
from common.vault_api import Vault
from infra.cluster_service import RESERVED_CLUSTERS, compute_properties, RESOURCE_CLUSTER
from infra.terraform_api import Terraform

ACCOUNTS_PATH = "secretv2/scalecube/spinless/accounts"
COMMON_PATH = "secretv2/scalecube/spinless/common"


class InfrastructureService:

    def __init__(self, app_logger):
        self.app_logger = app_logger
        pass

    def __setup_git_ssh(self):
        try:
            common_vault_data = Vault(self.app_logger).read(COMMON_PATH)["data"]
            # write git ssh keys to disk
            create_dirs("/root/.ssh")
            rsa_path = "/root/.ssh/id_rsa"
            with open(rsa_path, "w") as id_rsa:
                id_rsa_decoded = base64.standard_b64decode(common_vault_data['git_ssh_key']).decode("utf-8")
                id_rsa.write(id_rsa_decoded)
            rsa_pub_path = "/root/.ssh/id_rsa.pub"
            with open(rsa_pub_path, "w") as id_rsa_pub:
                id_rsa_pub_decoded = base64.standard_b64decode(common_vault_data['git_ssh_key_pub']).decode("utf-8")
                id_rsa_pub.write(id_rsa_pub_decoded)

            os.chmod(rsa_path, 0o400)
            os.chmod(rsa_pub_path, 0o400)
            shell_run('ssh-agent -s')
            shell_run('ssh-add /root/.ssh/id_rsa')

        except Exception as err:
            self.app_logger.error(f"Failed to write git keys from vault to disk: {str(err)}")

    def create_resource(self, job_ref, app_logger):
        try:
            request = job_ref.data
            required_params = ("type",
                               "name",
                               "account",
                               "properties")

            self.app_logger.info(f"Validating required parameters: {required_params}")
            if not all(k in request for k in required_params):
                return job_ref.complete_err(f'Not all mandatory params: {required_params}')

            #  Get secrets for account
            vault = Vault(logger=self.app_logger)
            account_data = vault.read(f"{ACCOUNTS_PATH}/{request['account']}")["data"]
            account = {"name": request['account'],
                       "aws_region": request.get("region"),
                       "aws_access_key": account_data.get("aws_access_key"),
                       "aws_secret_key": account_data.get("aws_secret_key"),
                       "aws_role_arn": account_data.get("aws_role_arn")}

            # Set up git ssh keys to access terraform modules in github
            self.__setup_git_ssh()

            # Calculate resource properties
            resource_type = request.get("type")
            resource_name = request.get("name")
            custom_resource_props = {}
            # Get custom common properties depending on resource_type
            if resource_type == RESOURCE_CLUSTER:
                custom_resource_props = compute_properties(app_logger)
            # Client request may override preconfigured common properties
            resource_properties = {**custom_resource_props, **request.get('properties')}

            terraform = Terraform(self.app_logger,
                                  resource_name,
                                  account,
                                  resource_properties,
                                  action="create",
                                  resource_type=resource_type)

            for (msg, res) in terraform.create_resource():
                if res is None:
                    job_ref.emit("RUNNING", msg)
                else:
                    if res == 0:
                        job_ref.complete_succ(f'Finished. Resource created successfully')
                    else:
                        job_ref.complete_err(f'Finished. Resource creation failed: {msg}')
                    break

        except Exception as ex:
            job_ref.complete_err(f'failed to create resource. Reason {ex}')

    def destroy_resource(self, job_ref, app_logger):
        try:
            request = job_ref.data
            required_params = ("type",
                               "name",
                               "account",
                               "region")

            # check mandatory params
            if not all(k in request for k in required_params):
                return job_ref.complete_err(f'Not all mandatory params: {required_params}')

            resource_name = request.get('name')
            resource_type = request.get('type')
            job_ref.emit(f"RUNNING: Start to destroy resource: {resource_name}", None)

            if resource_type == RESOURCE_CLUSTER and resource_name in RESERVED_CLUSTERS:
                return job_ref.complete_err(f"Please don't remove this {resource_type}: {resource_name}")

            #  Get secrets for account
            vault = Vault(logger=self.app_logger)
            account_data = vault.read(f"{ACCOUNTS_PATH}/{request['account']}")["data"]
            account = {"name": request['account'],
                       "aws_region": request.get("region"),
                       "aws_access_key": account_data.get("aws_access_key"),
                       "aws_secret_key": account_data.get("aws_secret_key"),
                       "aws_role_arn": account_data.get("aws_role_arn")}

            terraform = Terraform(self.app_logger,
                                  resource_name,
                                  account,
                                  request.get('properties'),
                                  action="destroy",
                                  resource_type=resource_type)

            for (msg, res) in terraform.destroy_resource():
                if res is None:
                    job_ref.emit("RUNNING", msg)
                else:
                    if res == 0:
                        job_ref.complete_succ(f'Finished. Resource deleted successfully')
                    else:
                        job_ref.complete_err(f'Finished. Resource deletion failed: {msg}')
                    break

        except Exception as ex:
            job_ref.complete_err(f'failed to delete resource. reason {ex}')

    def list_clusters(self):
        return KctxApi(self.app_logger).get_clusters_list()

    def get_namespaces(self, cluster_name):
        nss, code = KctxApi(self.app_logger).get_ns(cluster_name)
        if code != 0:
            return {"error": nss}
        return {"result": nss}

    def create_account(self, logger, account_name, aws_access_key, aws_secret_key):
        vault = Vault(logger)
        vault.write(f"{ACCOUNTS_PATH}/{account_name}",
                    aws_access_key=aws_access_key,
                    aws_secret_key=aws_secret_key)
        return {f"Account '{account_name}' created"}
