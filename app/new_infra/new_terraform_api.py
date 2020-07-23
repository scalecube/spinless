import base64
import json
import os
import shlex
import time

import boto3
from awscli.errorhandler import ClientError
from jinja2 import Environment, FileSystemLoader

from common.kube_api import KctxApi
from common.shell import shell_await, shell_run, create_dirs

KUBECONF_FILE = "kubeconfig"
TF_VARS_FILE = 'tfvars.tf'
AWS_VARS_FILE = 'aws_vars.tf'
BACKEND_FILE = 'backend.tf'


class Terraform:
    def __init__(self, logger, cluster_name, kctx_api, dns_suffix, aws_creds, tf_vars):
        self.logger = logger
        self.cluster_name = cluster_name
        self.kctx_api = kctx_api
        self.dns_suffix = dns_suffix
        self.aws_creds = aws_creds
        tf_vars.properties["eks"]["nodePools"] = json.dumps(tf_vars.properties["eks"]["nodePools"])
        self.tf_vars = tf_vars

        # calculated props
        timestamp = round(time.time() * 1000)
        self.work_dir = f'{os.getcwd()}/state/clusters/create-{cluster_name}-{timestamp}'
        create_dirs(self.work_dir)
        self.kube_config_file_path = f"{self.work_dir}/{KUBECONF_FILE}"
        self.templates = Environment(loader=FileSystemLoader("new_infra/templates"), trim_blocks=True)

        # cluster state properties
        # TODO: pass as parameters from POST request
        self.tf_dynamodb_table = "terraform-lock"  # dynamodb table used to lock states
        self.env = "dev"  # (dev/preprod/prod)
        self.tf_repository = "exberry-io/terraform-config-simple-aws"  # github repository with tf module to use
        self.tf_repository_version = "v0.1"  # version of release of github repo
        self.tf_s3_bucket = f'exberry-terraform-states-{self.env}'

    def create_cluster(self):
        self.logger.info(f"Started to create cluster in directory {self.work_dir}")
        # generate tf configuration files (using mapping between cluster type to github repo for tf files)
        self.__generate_backend_tf()
        self.__generate_main_tf()
        # generate tf vars (aws credentials and actually cloud configs)
        yield "RUNNING: Creating Terraform vars", None
        aws_vars_path = self._generate_aws_variables()
        cloud_vars_path = self.__generate_cluster_variables()

        # Terraform init
        _cmd_init = f"terraform init " \
                    f"-backend-config={self.work_dir}/{AWS_VARS_FILE}"
        yield "RUNNING: Initializing terraform...", None
        # Attention to "cwd=" that's important to work in same directory (/tmp/...)
        err, outp = shell_run(_cmd_init, cwd=self.work_dir, timeout=300)
        for s in outp:
            yield f"Terraform init: {s}", None
        if err != 0:
            yield f"FAILED: Failed to init terraform in dir {self.work_dir}", err
        else:
            yield "RUNNING: Terraform init complete", None

        # Terraform apply
        _cmd_apply = f"terraform apply -var-file={aws_vars_path} -var-file={cloud_vars_path} -auto-approve"
        yield f"RUNNING: Actually creating cluster. This may take time... {_cmd_apply}", None
        err_code_apply, outp = shell_await(shlex.split(_cmd_apply), with_output=True, cwd=self.work_dir,
                                           timeout=900)
        for s in outp:
            self.logger.info(s)
            yield f"Teraform apply: {s}", None
        self.logger.info(f"Terraform finished cluster creation. Errcode: {err_code_apply}")
        if err_code_apply != 0:
            yield "FAILED: Failed to create cluster", err_code_apply
        else:
            yield "RUNNING: Terraform has successfully created cluster", None

        for msg, status in self.__cluster_post_setup():
            yield msg, status
            if status is not None:
                break

        # If deployment was successful, save kubernetes context to vault
        kube_conf_str, err = KctxApi.generate_aws_kube_config(cluster_name=self.cluster_name,
                                                              aws_region=self.aws_creds.aws_region,
                                                              aws_access_key=self.aws_creds.aws_access_key,
                                                              aws_secret_key=self.aws_creds.aws_secret_key,
                                                              conf_path=self.kube_config_file_path
                                                              )
        if err == 0:
            yield "RUNNING: Kubernetes config generated successfully", None
        else:
            yield "ERROR: Failed to create kubernetes config", err

        kube_conf_base64 = base64.standard_b64encode(kube_conf_str.encode("utf-8")).decode("utf-8")
        self.kctx_api.save_aws_context(aws_access_key=self.aws_creds.aws_access_key,
                                       aws_secret_key=self.aws_creds.aws_secret_key,
                                       aws_region=self.aws_creds.aws_region,
                                       kube_cfg_base64=kube_conf_base64,
                                       cluster_name=self.cluster_name,
                                       dns_suffix=self.dns_suffix)
        yield "Saved cluster config.", None

        yield "Saving cluster parameters to S3...", None
        result = self.__save_cluster_to_s3(cloud_vars_path)
        if result:
            yield "Saving cluster parameters to S3: OK", None
        else:
            yield "Saving cluster parameters to S3: FAIL", None

    def _generate_aws_variables(self):
        f_name = f"{self.work_dir}/{AWS_VARS_FILE}"
        with open(f_name, "w") as aws_vars:
            aws_vars.write('{} = "{}"\n'.format("aws_region", self.aws_creds.aws_region))
            aws_vars.write('{} = "{}"\n'.format("aws_access_key", self.aws_creds.aws_access_key))
            aws_vars.write('{} = "{}"\n'.format("aws_secret_key", self.aws_creds.aws_secret_key))
        return f_name

    def __generate_cluster_variables(self):
        f_name = f"{self.work_dir}/tfvars.tf"
        with open(f_name, "w") as tfvars:
            gen_template = self.templates.get_template('template_tfvars.tf').render(
                variables=self.tf_vars)
            tfvars.write(gen_template)
        return f_name

    def __generate_backend_tf(self):
        f_name = f"{self.work_dir}/{BACKEND_FILE}"
        with open(f_name, "w") as file:
            gen_template = self.templates.get_template('template_backend.tf').render(
                bucket=self.tf_s3_bucket,
                cluster_name=self.tf_s3_bucket,
                dynamodb_table=self.tf_dynamodb_table)
            file.write(gen_template)
        return f_name

    def __generate_main_tf(self):
        f_name = f"{self.work_dir}/main.tf"
        with open(f_name, "w") as file:
            gen_template = self.templates.get_template('template_main.tf').render(
                repository=self.tf_repository,
                version=self.tf_repository_version)
            file.write(gen_template)
        return f_name

    def __generate_configmap(self):
        client = boto3.client('iam',
                              region_name=self.aws_creds.aws_region,
                              aws_access_key_id=self.aws_creds.aws_access_key,
                              aws_secret_access_key=self.aws_creds.aws_secret_key,
                              )
        role_arn = client.get_role(RoleName=f'eks-node-role-{self.cluster_name}')['Role']['Arn']
        f_name = f"{self.work_dir}/nodes_cm.yaml"
        with open(f_name, "w") as nodes_cm:
            gen_template = self.templates.get_template('nodes_cm.j2').render(aws_iam_role_eksnode_arn=role_arn)
            nodes_cm.write(gen_template)
        return f_name

    def __apply_node_auth_configmap(self, kube_env):
        self.__generate_configmap()
        kube_cmd = "kubectl apply -f {}/nodes_cm.yaml".format(self.work_dir)
        res, outp = shell_await(shlex.split(kube_cmd), env=kube_env, with_output=True)
        if res != 0:
            for s in outp:
                self.logger.info(s)
            return res, "Failed to create nodes_cm"
        return res, outp

    def __cluster_post_setup(self):
        # Generate cluster config
        yield "RUNNING: Generating kubernetes cluster config...", None
        kube_env = {"KUBECONFIG": self.kube_config_file_path,
                    "AWS_DEFAULT_REGION": self.aws_creds.aws_region,
                    "AWS_ACCESS_KEY_ID": self.aws_creds.aws_access_key,
                    "AWS_SECRET_ACCESS_KEY": self.aws_creds.aws_secret_key
                    }
        # Apply node auth confmap
        yield "RUNNING: Applying node auth configmap...", None
        auth_conf_map_result, msg = self.__apply_node_auth_configmap(kube_env)
        if auth_conf_map_result != 0:
            yield "FAILED: Failed to apply node config map...", auth_conf_map_result
        else:
            yield "SUCCESS: Cluster creation and conf setup complete", None

        # Provision Vault
        vault_prov_res, msg = self.kctx_api.provision_vault(self.cluster_name, self.work_dir, kube_env)
        if vault_prov_res != 0:
            yield "FAILED: Failed setup vault account in new cluster. Aborting: {}".format(msg), vault_prov_res
        yield "Vault provisioning complete", None

        # Set up storage
        storage_res, msg = self.kctx_api.setup_storage(kube_env, self.work_dir)
        if storage_res != 0:
            yield "FAILED: Failed to setup storage volume. Aborting: {}".format(msg), storage_res
        yield "Storage volume set up successfully.", None

        #  Setup cluster autoscaler
        ca, msg = self.kctx_api.setup_ca(kube_env, self.cluster_name, self.aws_creds.aws_region)
        if ca != 0:
            yield "Failed to setup cluster autoscaler. Resuming anyway", None
        else:
            yield "Cluster autoscaler installed successfully.", None

        # Set up traefik
        traefik_res, msg = self.kctx_api.setup_traefik(kube_env)
        if traefik_res != 0:
            yield "Failed to setup traefik. Resuming anyway", None
        else:
            yield "Traefik installed successfully.", None

        # Set up metrics
        res, msg = self.kctx_api.setup_metrics(kube_env)
        if res != 0:
            yield "FAILED: Failed to setup metrics. Aborting: {}".format(msg), None  # TODO: res
        yield "Metrics installed successfully.", None

    def destroy_cluster(self):
        self.logger.info("Destroy cluster mock")
        yield "Functionality not implemented yet", None

    def __save_cluster_to_s3(self, cloud_vars_path):
        cluster_info_path = f"{self.work_dir}/cluster_info.yaml"
        with open(cluster_info_path, "w") as file:
            gen_template = self.templates.get_template('template_cluster_info.yaml').render(
                env=self.env,
                github_module_ref=self.tf_repository,
                github_module_version=self.tf_repository_version)
            file.write(gen_template)
        s3_client = boto3.client('s3',
                                 region_name=self.aws_creds.aws_region,
                                 aws_access_key_id=self.aws_creds.aws_access_key,
                                 aws_secret_access_key=self.aws_creds.aws_secret_key,
                                 )
        env_path = f"environments/{self.cluster_name}"
        try:
            s3_client.upload_file(cloud_vars_path, self.tf_s3_bucket, f"{env_path}/tfvars.tf")
            s3_client.upload_file(cluster_info_path, self.tf_s3_bucket, f"{env_path}/cluster_info.yaml")
        except ClientError as e:
            self.logger.error(e)
            return False
        return True
