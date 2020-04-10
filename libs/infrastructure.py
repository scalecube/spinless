import os
import sys
import time
from subprocess import Popen, PIPE

import boto3
from jinja2 import Environment, FileSystemLoader

from libs.kube_api import KctxApi

KUBECONF_FILE = "kubeconfig"
TF_VARS_FILE = 'tfvars.tf'


class TF:
    def __init__(self, logger, aws_region, aws_access_key,
                 aws_secret_key, cluster_name, az1, az2,
                 kube_nodes_amount, kube_nodes_instance_type):
        self.logger = logger
        curr_dir = os.path.dirname(sys.modules['__main__'].__file__)
        timestamp = round(time.time() * 1000)
        self.tf_working_dir = "{}/{}".format(curr_dir, os.getenv('TF_WORKING_DIR'))
        self.cwd = "{}/{}".format(curr_dir, os.getenv('TF_STATE'))
        self.tmp_root_path = "/tmp/{}".format(timestamp)
        self.aws_region = aws_region
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.cluster_name = cluster_name
        self.az1 = az1
        self.az2 = az2
        self.kube_nodes_amount = kube_nodes_amount
        self.kube_nodes_instance_type = kube_nodes_instance_type

    def __create_vars_file(self):
        with open("{}/tfvars.tf".format(self.tmp_root_path), "w") as tfvars:
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

    def generate_configmap(self):
        client = boto3.client('iam')
        role_arn = client.get_role(RoleName='eks-node-role')['Role']['Arn']
        with open("{}/nodes_cm.yaml".format(self.tmp_root_path), "w") as nodes_cm:
            j2_env = Environment(loader=FileSystemLoader("/opt/templates/"),
                                 trim_blocks=True)
            gen_template = j2_env.get_template('nodes_cm.j2').render(aws_iam_role_eksnode_arn=role_arn)
            nodes_cm.write(gen_template)

    def __apply_node_auth_configmap(self):
        self.generate_configmap()
        process = Popen(['kubectl', 'apply', "-f",
                         "{}/nodes_cm.yaml".format(self.tmp_root_path)],
                        env=dict(os.environ,
                                 **{"KUBECONFIG": self.kube_config_file}),
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        return process.wait()

    def install_kube(self):
        os.mkdir(self.tmp_root_path)
        _cmd_wksps = ['terraform', 'workspace', 'new', self.cluster_name, self.tf_working_dir]
        yield "START: Creating Workspace: {}".format(_cmd_wksps), None
        process = Popen(_cmd_wksps, cwd=self.cwd,
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        self.logger.info("Create namespace")
        time.sleep(2)
        self.logger.info("stdout id: {}".format(stdout))
        self.logger.info("stderr id: {}".format(stderr))
        process.wait()
        yield "RUNNING: Terraform workspace created: {}", None

        yield "RUNNING: Creating Terraform vars", None
        self.__create_vars_file()
        yield "RUNNING: Terraform vars created", None
        _cmd_apply = ['terraform',
                      'apply',
                      '-var-file={}/{}'.format(self.tmp_root_path, TF_VARS_FILE),
                      '-auto-approve',
                      self.tf_working_dir]
        yield "RUNNING: Actually creating cloud. This may take time... {}".format(_cmd_apply), None
        process = Popen(_cmd_apply, cwd=self.cwd,
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        time.sleep(10)
        self.logger.info("stdout tf apply: {}".format(stdout))
        self.logger.info("stderr tf apply: {}".format(stderr))
        err_code_apply = process.wait(timeout=900)
        self.logger.info("Terraform finished cluster creation. Errcode: {}".format(err_code_apply))
        if err_code_apply != 0:
            yield "FAILED: Failed to create cluster", err_code_apply
        else:
            yield "RUNNING: Terraform has successfully created cluster", None

        yield "RUNNING: Setting aws config", None
        aws_conf_result = self.__set_aws_cli_config()
        if aws_conf_result != 0:
            yield "FAILED: Failed to create aws config", 1
        else:
            yield "RUNNING: AWS config set successfully", None

        yield "RUNNING: Generating cluster config...", None
        KctxApi.generate_cluster_config(cluster_name=self.cluster_name,
                                        config_file="{}/{}".format(self.tmp_root_path, KUBECONF_FILE))
        yield "RUNNING: Generated cluster config: success", None

        yield "RUNNING: Applying node auth configmap...", None
        auth_conf_map_result = self.__apply_node_auth_configmap()
        if auth_conf_map_result != 0:
            yield "FAILED: Failed to apply node config map...", auth_conf_map_result
        else:
            yield "SUCCESS: Cluster creation and conf setup complete", 0
