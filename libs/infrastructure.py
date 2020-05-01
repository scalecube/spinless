import base64
import os
import shlex
import time
from subprocess import Popen, PIPE

import boto3
from jinja2 import Environment, FileSystemLoader

from libs.kube_api import KctxApi
from libs.shell import shell_await

KUBECONF_FILE = "kubeconfig"
TF_VARS_FILE = 'tfvars.tf'


class TF:
    def __init__(self, logger, aws_region, aws_access_key,
                 aws_secret_key, cluster_name, az1, az2,
                 kube_nodes_amount, kube_nodes_instance_type, kctx_api, dns_suffix):
        self.logger = logger
        curr_dir = os.getcwd()
        timestamp = round(time.time() * 1000)
        self.tf_working_dir = "{}/{}".format(curr_dir, os.getenv('TF_WORKING_DIR'))
        self.tf_state_dir = "{}/{}".format(curr_dir, os.getenv('TF_STATE'))
        self.tmp_root_path = "/tmp/{}".format(timestamp)
        os.mkdir(self.tmp_root_path)
        self.kube_config_file_path = "{}/{}".format(self.tmp_root_path, KUBECONF_FILE)
        self.aws_region = aws_region
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.cluster_name = cluster_name
        self.az1 = az1
        self.az2 = az2
        self.kube_nodes_amount = kube_nodes_amount
        self.kube_nodes_instance_type = kube_nodes_instance_type
        self.kctx_api = kctx_api
        self.dns_suffix = dns_suffix

    def __create_vars_file(self):
        with open("{}/tfvars.tf".format(self.tmp_root_path), "w") as tfvars:
            self.logger.info("tfvars file is: {}/tfvars.tf".format(self.tmp_root_path))
            tfvars.write('{} = "{}"\n'.format("aws_region", self.aws_region))
            tfvars.write('{} = "{}"\n'.format("aws_access_key", self.aws_access_key))
            tfvars.write('{} = "{}"\n'.format("aws_secret_key", self.aws_secret_key))
            tfvars.write('{} = "{}"\n'.format("cluster-name", self.cluster_name))
            tfvars.write('{} = "{}"\n'.format("az1", self.az1))
            tfvars.write('{} = "{}"\n'.format("az2", self.az2))
            tfvars.write('{} = "{}"\n'.format("kube_nodes_amount", self.kube_nodes_amount))
            tfvars.write('{} = "{}"\n'.format("kube_nodes_instance_type", self.kube_nodes_instance_type))

    def __set_aws_cli_config(self):
        result = 0
        process = Popen(["aws", "configure", "set", "aws_access_key_id",
                         "{}".format(self.aws_access_key)], stdout=PIPE, stderr=PIPE)
        result += process.wait()
        process = Popen(["aws", "configure",
                         "set", "aws_secret_access_key",
                         "{}".format(self.aws_secret_key)], stdout=PIPE, stderr=PIPE)
        result += process.wait()

        process = Popen(["aws", "configure",
                         "set", "default.region",
                         "{}".format(self.aws_region)], stdout=PIPE, stderr=PIPE)
        return result + process.wait()

    def __generate_configmap(self):
        client = boto3.client('iam',
                              region_name=self.aws_region,
                              aws_access_key_id=self.aws_access_key,
                              aws_secret_access_key=self.aws_secret_key,
                              )
        role_arn = client.get_role(RoleName='eks-node-role-{}'.format(self.cluster_name))['Role']['Arn']
        with open("{}/nodes_cm.yaml".format(self.tmp_root_path), "w") as nodes_cm:
            j2_env = Environment(loader=FileSystemLoader("/opt/templates/"),
                                 trim_blocks=True)
            gen_template = j2_env.get_template('nodes_cm.j2').render(aws_iam_role_eksnode_arn=role_arn)
            nodes_cm.write(gen_template)

    def __apply_node_auth_configmap(self, kube_env):
        self.__generate_configmap()
        kube_cmd = "kubectl apply -f {}/nodes_cm.yaml".format(self.tmp_root_path)
        res, outp = shell_await(kube_cmd, env=kube_env, with_output=True)
        if res != 0:
            for s in outp:
                self.logger.info(s)
            return res, "Failed to create nodes_cm"
        return res, outp

    def install_kube(self):
        # Create terraform workspace
        _cmd_wksps = 'terraform workspace new {} {}'.format(self.cluster_name, self.tf_working_dir)
        yield "START: Creating Workspace: {}".format(_cmd_wksps), None
        wksp_res, outp = shell_await(shlex.split(_cmd_wksps), with_output=True, cwd=self.tf_state_dir)
        for s in outp:
            self.logger.info(s)
            yield "Creating workspace: {}".format(s), None
        yield "RUNNING: Terraform workspace created: {}", None

        # Create terraform vars
        yield "RUNNING: Creating Terraform vars", None
        self.__create_vars_file()
        yield "RUNNING: Terraform vars created", None

        # Terraform apply - actual creation of cluster
        _cmd_apply = "terraform apply -var-file={}/{} -auto-approve {}".format(self.tmp_root_path, TF_VARS_FILE,
                                                                               self.tf_working_dir)
        yield "RUNNING: Actually creating cloud. This may take time... {}".format(_cmd_apply), None
        err_code_apply, outp = shell_await(shlex.split(_cmd_apply), with_output=True, cwd=self.tf_state_dir,
                                           timeout=900)
        for s in outp:
            self.logger.info(s)
            yield "Creating cluster: {}".format(s), None
        self.logger.info("Terraform finished cluster creation. Errcode: {}".format(err_code_apply))
        if err_code_apply != 0:
            yield "FAILED: Failed to create cluster", err_code_apply
        else:
            yield "RUNNING: Terraform has successfully created cluster", None

        # Generate cluster config
        yield "RUNNING: Generating kubernetes cluster config...", None
        kube_conf_str, err = KctxApi.generate_aws_kube_config(cluster_name=self.cluster_name,
                                                              aws_region=self.aws_region,
                                                              aws_access_key=self.aws_access_key,
                                                              aws_secret_key=self.aws_secret_key,
                                                              conf_path=self.kube_config_file_path
                                                              )
        if err == 0:
            yield "RUNNING: Kubernetes config generated successfully", None
        else:
            yield "ERROR: Failed to create kubernetes config", err

        kube_env = {"KUBECONFIG": self.kube_config_file_path,
                    "AWS_DEFAULT_REGION": self.aws_region,
                    "AWS_ACCESS_KEY_ID": self.aws_access_key,
                    "AWS_SECRET_ACCESS_KEY": self.aws_secret_key
                    }
        # Apply node auth confmap
        yield "RUNNING: Applying node auth configmap...", None
        auth_conf_map_result, msg = self.__apply_node_auth_configmap(kube_env)
        if auth_conf_map_result != 0:
            yield "FAILED: Failed to apply node config map...", auth_conf_map_result
        else:
            yield "SUCCESS: Cluster creation and conf setup complete", None

        # Provision Vault
        vault_prov_res, msg = self.kctx_api.provision_vault(self.cluster_name, self.tmp_root_path, kube_env)
        if vault_prov_res != 0:
            yield "FAILED: Failed setup vault account in new cluster. Aborting: {}".format(msg), vault_prov_res
        yield "Vault provisioning complete", None

        # Set up storage
        storage_res, msg = self.kctx_api.setup_storage(kube_env, self.tmp_root_path)
        if storage_res != 0:
            yield "FAILED: Failed to setup storage volume. Aborting: {}".format(msg), storage_res
        yield "Storage volume set up successfully.", None

        # Set up traefik
        traefik_res, msg = self.kctx_api.setup_traefik(kube_env)
        if traefik_res != 0:
            yield "Failed to setup traefik. Resuming anyway", None
        else:
            yield "Traefik initialized successfully.", None

        # Set up metrics
        res, msg = self.kctx_api.setup_metrics(kube_env)
        if res != 0:
            yield "FAILED: Failed to setup metrics. Aborting: {}".format(msg), res
        yield "Metrics initialized successfully.", None

        # If deployment was successful, save kubernetes context to vault
        kube_conf_base64 = base64.standard_b64encode(kube_conf_str.encode("utf-8")).decode("utf-8")
        self.kctx_api.save_aws_context(self.aws_access_key, self.aws_secret_key, self.aws_region, kube_conf_base64,
                                       self.cluster_name, self.dns_suffix)

        yield "Saved cluster config.", None
