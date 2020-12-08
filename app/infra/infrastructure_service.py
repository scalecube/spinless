import base64
import os

from common.kube_api import KctxApi
from common.shell import create_dirs, shell_run
from common.vault_api import Vault
from infra.cluster_service import compute_properties, RESOURCE_CLUSTER
from infra.terraform_api import Terraform

ACCOUNTS_PATH = "secretv2/scalecube/spinless/accounts"
COMMON_PATH = "secretv2/scalecube/spinless/common"
COMMON_RESOURCES_PART = "secretv2/scalecube/spinless/resources/common"


class InfrastructureService:

    def __init__(self, app_logger):
        self.app_logger = app_logger
        pass

    def create_resource(self, job_ref, app_logger):
        """
        Create resource of given type/name with given properties.

        Properties that are passed to terraform are calculated following the rules:

        1 - read properties common to all resources in Valut under 'resources/common' path. They contain:
            s3_bucket - bucket name where states are kept
            tf_dynamodb_table - name of Dynamodb table that is used for state access synchronization
        2 - read properties specific to resource type in vault under 'resources/${type}'
        3 - override/enrich the properties with ones passed in request. Any property matching the one that was read in
            vault will have priority
        :param job_ref: job reference with data that has mandatory parameters:
                "type", "name", "account", "properties"
        :param app_logger: logger

        """
        try:
            request = job_ref.data
            required_params = ("type",
                               "name",
                               "account",
                               "properties")

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
            common_resource_properties = vault.read(COMMON_RESOURCES_PART)["data"]
            custom_resource_props = {}
            # Get custom common properties depending on resource_type
            if resource_type == RESOURCE_CLUSTER:
                custom_resource_props = compute_properties(app_logger)
            # Client request may override preconfigured common properties
            resource_properties = {**custom_resource_props, **request.get('properties')}
            resource_properties.update(common_resource_properties)

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
