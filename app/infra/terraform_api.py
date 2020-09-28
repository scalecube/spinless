import os
import time

import boto3

from common.shell import shell_run, create_dirs
# TODO: pass as parameters from POST request
from infra.cluster_service import *

INFRA_TEMPLATES_ROOT = "infra/templates"
KUBECONF_FILE = "kubeconfig"
BACKEND_FILE = 'backend.tf'


class Terraform:
    def __init__(self, logger=None, name=None, account=None, properties=None, action="UNKNOWN", resource_type=None):
        self.logger = logger
        self.resource_name = name
        self.resource_type = resource_type
        self.account = account
        self.properties = properties
        self.account_name = account['name']  # (develop/staging/production)

        # calculated props
        timestamp = round(time.time() * 1000)
        self.work_dir = f'{os.getcwd()}/state/{resource_type}/{action}-{name}-{timestamp}'
        create_dirs(self.work_dir)
        self.kube_config_file_path = f"{self.work_dir}/{KUBECONF_FILE}"
        self.templates = Environment(loader=FileSystemLoader("infra/templates"), trim_blocks=True)
        self.kctx_api = KctxApi(logger)

        # cluster state properties
        self.tf_dynamodb_table = properties['tf_dynamodb_table']  # dynamodb table used to lock states
        self.tf_repository = properties['tf_repo']  # github repository with tf module to use
        self.tf_repository_version = properties['tf_repo_version']  # version of release of github repo
        self.tf_s3_bucket_name = properties['s3_bucket']  # version of release of github repo
        self.s3_path = f"{self.account_name}/{resource_type}/{self.resource_name}"
        self.s3_client = self.__init_s3_client(self.account)

    def create_resource(self):
        self.logger.info(f"Started to create resource in directory {self.work_dir}")
        self.__generate_backend_tf()
        yield "RUNNING: Creating Terraform vars", None
        _, resource_vars = self.__read_environment()
        if resource_vars:
            yield f"Resource {self.resource_type}/{self.resource_name} exists, using its state and variables", None
            # User request may override some existing properties
            self.properties = {**resource_vars, **self.properties}

        aws_vars_path, resource_vars_path, variables = "", "", {}
        if self.resource_type == RESOURCE_CLUSTER:
            aws_vars_path, resource_vars_path, variables = props_to_tfvars(self.work_dir, self.account,
                                                                           self.resource_name,
                                                                           self.properties)
        yield "New resource is being created. Generated tf vars", None
        self.__generate_tf_configs(variables)

        # Terraform init
        yield "RUNNING: Initializing terraform...", None
        # Attention to "cwd=" that's important to work in same directory (/tmp/...)
        err, outp = shell_run("terraform init -no-color", cwd=self.work_dir, timeout=300)
        for s in outp:
            yield f"Terraform init: {s}", None
        if err != 0:
            yield f"FAILED: Failed to init terraform in dir {self.work_dir}", err
        else:
            yield "RUNNING: Terraform init complete", None

        # Need to have same exact variables.tf in parent dir, as in module
        shell_run(f"cp {self.work_dir}/.terraform/modules/{self.resource_name}/variables.tf {self.work_dir}/")

        yield "Saving resource parameters to S3...", None
        result = self.__save_resource_to_s3(resource_vars_path)
        if result:
            yield "Saving resource parameters to S3: OK", None
        else:
            yield "Saving resource parameters to S3: FAIL", None

        # Terraform apply
        _cmd_apply = f"terraform apply -no-color -var-file={aws_vars_path} -var-file={resource_vars_path} -auto-approve"
        yield f"RUNNING: Actually CREATING resource. This may take time... {_cmd_apply}", None
        err_code_apply, outp = shell_run(_cmd_apply, cwd=self.work_dir, timeout=900)
        for s in outp:
            self.logger.info(s)
            yield f"Terraform apply: {s}", None
        self.logger.info(f"Terraform finished resource creation. Errcode: {err_code_apply}")
        if err_code_apply != 0:
            yield "FAILED: Failed to create resource", None
            # Destroy partially created resources if failed to finis apply
            _cmd_destroy = f"terraform destroy -no-color" \
                           f" -var-file={aws_vars_path} -var-file={resource_vars_path} -auto-approve"
            yield f"RUNNING: DESTROYING partially created resource. This may take time... {_cmd_destroy}", None
            err_code_destroy, outp = shell_run(_cmd_destroy, cwd=self.work_dir, timeout=900)
            for s in outp:
                self.logger.info(s)
            self.logger.info(f"Terraform destroy complete. Errcode: {err_code_destroy}")
            yield "FAILED: Failed to create resource", err_code_apply
        else:
            yield "RUNNING: Terraform has successfully created resource", None

        if self.resource_type == RESOURCE_CLUSTER:
            for msg, status in resource_post_setup(self):
                if status is not None:
                    if status == 0:
                        yield msg, None
                        break
                    else:
                        yield msg, status
                yield msg, status
        yield "success", 0

    def destroy_resource(self):
        self.logger.info(f"Started to DESTROY cluster {self.resource_name}  in directory {self.work_dir}")
        # generate tf backend
        self.__generate_backend_tf()

        resource_vars_path, resource_vars = self.__read_environment()
        if not resource_vars_path or not resource_vars:
            yield f"FAILED: cluster {self.account_name}/{self.resource_name} does not exist", 1

        aws_vars_path, _, aws_vars = "", "", {}
        if self.resource_type == RESOURCE_CLUSTER:
            aws_vars_path, _, aws_vars = props_to_tfvars(self.work_dir, self.account, self.resource_name)

        self.__generate_tf_configs(aws_vars + list(resource_vars.keys()))

        # Terraform init
        _cmd_init = f"terraform init -no-color"
        yield "RUNNING: Initializing terraform...", None
        # Attention to "cwd=" that's important to work in same directory (/tmp/...)
        err, outp = shell_run(_cmd_init, cwd=self.work_dir, timeout=300)
        for s in outp:
            yield f"Terraform init: {s}", None
        if err != 0:
            yield f"FAILED: Failed to init terraform in dir {self.work_dir}", err
        else:
            yield "RUNNING: Terraform init complete", None

        shell_run(f"cp {self.work_dir}/.terraform/modules/{self.resource_name}/variables.tf {self.work_dir}/")

        _cmd_destroy = f"terraform destroy -no-color" \
                       f" -var-file={aws_vars_path} -var-file={resource_vars_path} -auto-approve"
        yield f"RUNNING: Actually DESTROYING resources. This may take time... {_cmd_destroy}", None
        err_code_destroy, outp = shell_run(_cmd_destroy, cwd=self.work_dir, timeout=900)
        for s in outp:
            self.logger.info(s)
            yield f"Terraform destroy: {s}", None
        self.logger.info(f"Terraform destroy complete. Errcode: {err_code_destroy}")
        if err_code_destroy != 0:
            yield "FAILED: Failed to destroy cluster", err_code_destroy
        else:
            yield "RUNNING: Terraform has successfully destroyed cluster", None

        for msg, status in resource_post_destroy(self):
            yield msg, status
            if status is not None:
                break

        yield "Clearing cluster parameters from S3...", None
        result = self.__delete_resource_from_s3()
        if result:
            yield "Delete cluster parameters from S3: OK", None
        else:
            yield "Delete cluster parameters from S3: FAIL", None

        yield "success", 0

    def __read_environment(self):
        """
        Checks if terraform.state exists
        Then reads tf vars from s3 bucket
        :return: path to downloaded tfvars, and tfvars keys (var names)
        """
        try:
            # check if state exists:
            if self._s3_key_exists(f"{self.s3_path}/terraform.tfstate") is None:
                return False, False
            # download variables (if fails - return False
            f_name = f'{self.work_dir}/resource.tfvars'
            self.s3_client.download_file(self.tf_s3_bucket_name, f"{self.s3_path}/resource.tfvars", f_name)
            # extract dictionary from var file
            variables_dict = self.__vars_file_to_dict(f_name)
            if variables_dict:
                return f_name, variables_dict
            else:
                return False, False
        except Exception as e:
            self.logger.error(e)
            return False, False

    def _s3_key_exists(self, key):
        """
        return the key's size if it exist, else None
        """
        response = self.s3_client.list_objects_v2(
            Bucket=self.tf_s3_bucket_name,
            Prefix=key,
        )
        for obj in response.get('Contents', []):
            if obj['Key'] == key:
                return obj['Size']

    def __generate_backend_tf(self):
        f_name = f"{self.work_dir}/{BACKEND_FILE}"
        with open(f_name, "w") as file:
            gen_template = self.templates.get_template('template_backend.tf').render(
                bucket=self.tf_s3_bucket_name,
                resource_path=self.s3_path,
                region=self.account["aws_region"],
                access_key=self.account["aws_access_key"],
                secret_key=self.account["aws_secret_key"],
                role_arn=self.account["aws_role_arn"],
                dynamodb_table=self.tf_dynamodb_table)
            file.write(gen_template)
        return f_name

    def __generate_tf_configs(self, all_variables):
        f_name = f"{self.work_dir}/main.tf"
        with open(f_name, "w") as file:
            gen_template = self.templates.get_template('template_main.tf').render(
                module_name=self.resource_name,
                repository=self.tf_repository,
                version=self.tf_repository_version,
                variables=all_variables)
            file.write(gen_template)
        return f_name

    def generate_configmap(self):
        client = boto3.client('iam',
                              region_name=self.account["aws_region"],
                              aws_access_key_id=self.account["aws_access_key"],
                              aws_secret_access_key=self.account["aws_secret_key"],
                              )
        role_arn = client.get_role(RoleName=f'eks-node-role-{self.resource_name}')['Role']['Arn']
        f_name = f"{self.work_dir}/nodes_cm.yaml"
        with open(f_name, "w") as nodes_cm:
            gen_template = self.templates.get_template('nodes_cm.j2').render(aws_iam_role_eksnode_arn=role_arn)
            nodes_cm.write(gen_template)
        return f_name

    def apply_node_auth_configmap(self, kube_env):
        self.generate_configmap()
        kube_cmd = f"kubectl apply -f {self.work_dir}/nodes_cm.yaml"
        res, outp = shell_run(kube_cmd, env=kube_env)
        if res != 0:
            for s in outp:
                self.logger.info(s)
            return res, "Failed to create nodes_cm"
        return res, outp

    def __save_resource_to_s3(self, resource_vars_path):
        resource_info_path = f"{self.work_dir}/resource_info.yaml"
        with open(resource_info_path, "w") as file:
            gen_template = self.templates.get_template('template_resource_info.yaml').render(
                account=self.account_name,
                resource_name=self.resource_name,
                resource_type=self.resource_type,
                github_module_ref=self.tf_repository,
                github_module_version=self.tf_repository_version)
            file.write(gen_template)
        try:
            self.s3_client.upload_file(resource_vars_path, self.tf_s3_bucket_name, f"{self.s3_path}/resource.tfvars")
            self.s3_client.upload_file(resource_info_path, self.tf_s3_bucket_name, f"{self.s3_path}/resource_info.yaml")
        except Exception as e:
            self.logger.error(e)
            return False
        return True

    def __delete_resource_from_s3(self):
        try:
            self.s3_client.delete_object(Bucket=self.tf_s3_bucket_name, Key=f"{self.s3_path}")
            self.s3_client.delete_object(Bucket=self.tf_s3_bucket_name, Key=f"states/{self.resource_name}")
        except Exception as e:
            self.logger.error(e)
            return False
        return True

    def __vars_file_to_dict(self, file):
        try:
            result = {}
            with open(file, 'r') as reader:
                for line in reader.readlines():
                    key_val = line.rstrip().split(" = ")
                    result[key_val[0]] = key_val[1].strip('"')
            return result
        except Exception as ex:
            self.logger.warn(f"Error while getting keys from variables file: {ex}")
            return None

    def __init_s3_client(self, account):
        session = boto3.Session(aws_access_key_id=account['aws_access_key'],
                                aws_secret_access_key=account['aws_secret_key'])
        sts_client = session.client('sts')
        temp_credentials = sts_client.assume_role(RoleArn=account['aws_role_arn'],
                                                  RoleSessionName="name",
                                                  DurationSeconds=3600)

        session = boto3.Session(
            aws_access_key_id=temp_credentials['Credentials']['AccessKeyId'],
            aws_secret_access_key=temp_credentials['Credentials']['SecretAccessKey'],
            aws_session_token=temp_credentials['Credentials']['SessionToken'])

        return session.client('s3')
