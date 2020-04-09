import os
import time
import boto3
from jinja2 import Environment, FileSystemLoader
from subprocess import Popen, PIPE
from libs.kube_api import KctxApi


class TF:
    def __init__(self, logger, aws_region, aws_access_key,
                 aws_secret_key, cluster_name, az1, az2,
                 kube_nodes_amount, kube_nodes_instance_type):
        self.logger = logger
        self.working_dir = os.getenv('TF_WORKING_DIR')
        self.cwd = os.getenv('TF_STATE')
        self.aws_region = aws_region
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.cluster_name = cluster_name
        self.az1 = az1
        self.az2 = az2
        self.kube_nodes_amount = kube_nodes_amount
        self.kube_nodes_instance_type = kube_nodes_instance_type
        self.timestamp = round(time.time() * 1000)
        self.working_dir = os.getenv('TF_WORKING_DIR')
        self.kube_config_file = "/tmp/{}/kubeconfig".format(self.timestamp)

    def create_vars_file(self):
        os.mkdir("/tmp/{}".format(self.timestamp))
        with open("/tmp/{}/tfvars.tf".format(self.timestamp), "w") as tfvars:
            tfvars.write('{} = "{}"\n'.format("aws_region", self.aws_region))
            tfvars.write('{} = "{}"\n'.format("aws_access_key", self.aws_access_key))
            tfvars.write('{} = "{}"\n'.format("aws_secret_key", self.aws_secret_key))
            tfvars.write('{} = "{}"\n'.format("clustername", self.cluster_name))
            tfvars.write('{} = "{}"\n'.format("az1", self.az1))
            tfvars.write('{} = "{}"\n'.format("az2", self.az2))
            tfvars.write('{} = "{}"\n'.format("kube_nodes_amount", self.kube_nodes_amount))
            tfvars.write('{} = "{}"\n'.format("kube_nodes_instance_type", self.kube_nodes_instance_type))

    def set_aws_cli_config(self):
        process = Popen(["aws", "configure", "set", "aws_access_key_id",
                         "".format(self.aws_access_key)], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        process.wait()

        process = Popen(["aws", "configure",
                         "set", "aws_secret_access_key",
                         "{}".format(self.aws_secret_key)], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        process.wait()

        process = Popen(["aws", "configure",
                         "set", "default.region",
                         "{}".format(self.aws_region)], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        process.wait()

    def generate_configmap(self):
        client = boto3.client('iam')
        role_arn = client.get_role(RoleName='eks-node-role')['Role']['Arn']
        with open("/tmp/{}/nodes_cm.yaml", "w") as nodes_cm:
            j2_env = Environment(loader=FileSystemLoader("/opt/templates/"),
                                 trim_blocks=True)
            gen_template = j2_env.get_template('nodes_cm.j2').render(aws_iam_role_eksnode_arn=role_arn)
            nodes_cm.write(gen_template)

    def apply_node_auth_configmap(self):
        self.generate_configmap()
        process = Popen(['kubectl', 'apply', "-f",
                         "/tmp/{}/nodes_cm.yaml"],
                        env=dict(os.environ,
                                 **{"KUBECONFIG": self.kube_config_file}),
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        process.wait()

    def install_kube(self):
        process = Popen(['terraform', 'workspace', 'new', self.cluster_name, self.working_dir], cwd=self.cwd,
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        self.logger.info("Create namespace")
        time.sleep(2)
        self.logger.info("stdout id: {}".format(stdout))
        self.logger.info("stderr id: {}".format(stderr))
        process.wait()
        self.create_vars_file()
        process = Popen(['terraform',
                         'apply',
                         '-var-file=/tmp/{}/tfvars.tf'.format(self.timestamp),
                         '-auto-approve',
                         self.working_dir], cwd=self.cwd,
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        time.sleep(10)
        self.logger.info("stdout tf apply: {}".format(stdout))
        self.logger.info("stderr tf apply: {}".format(stderr))
        process.wait(timeout=900)
        self.logger.info("Terraform finished cluster creation")
        self.set_aws_cli_config()
        KctxApi.generate_cluster_config(cluster_name=self.cluster_name,
                                        config_file=self.kube_config_file)
        self.apply_node_auth_configmap()
