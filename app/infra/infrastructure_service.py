import base64
import os

from common.kube_api import KctxApi
from common.shell import create_dirs, shell_run
from common.vault_api import Vault
from infra.cluster_service import compute_properties, RESOURCE_CLUSTER
from infra.terraform_api import Terraform

class InfrastructureService:

    def __init__(self, app_logger):
        self.app_logger = app_logger
        pass

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
            vault = Vault(logger=self.app_logger)
            common_resource_properties = vault.read(COMMON_RESOURCES_PART)["data"]
            resource_properties = compute_properties(app_logger, creating_resource=False)
            if resource_type == RESOURCE_CLUSTER and resource_name in resource_properties.get("reserved_clusters", []):
                return job_ref.complete_err(f"Please don't remove this {resource_type}: {resource_name}")

            #  Get secrets for account

            account_data = vault.read(f"{ACCOUNTS_PATH}/{request['account']}")["data"]
            account = {"name": request['account'],
                       "aws_region": request.get("region"),
                       "aws_access_key": account_data.get("aws_access_key"),
                       "aws_secret_key": account_data.get("aws_secret_key"),
                       "aws_role_arn": account_data.get("aws_role_arn")}

            properties = {**common_resource_properties, **resource_properties, **request.get('properties', {})}

            terraform = Terraform(self.app_logger,
                                  resource_name,
                                  account,
                                  properties,
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

    def create_account(self, logger, account_name, aws_access_key, aws_secret_key):
        vault = Vault(logger)
        vault.write(f"{ACCOUNTS_PATH}/{account_name}",
                    aws_access_key=aws_access_key,
                    aws_secret_key=aws_secret_key)
        return {f"Account '{account_name}' created"}
