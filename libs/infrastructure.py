import os
import time
from subprocess import Popen, PIPE


class TF:
    def __init__(self, workspace, aws_region,
                 aws_access_key, aws_secret_key, clustername,
                 az1, az2, kube_nodes_amount, kube_nodes_instance_type):
        self.working_dir = os.getenv('TF_WORKING_DIR')
        self.workspace = workspace
        self.aws_region = aws_region
        self.aws_access_key = aws_access_key
        self.aws_secret_key= aws_secret_key
        self.clustername = clustername
        self.az1 = az1
        self.az2 = az2
        self.kube_nodes_amount = kube_nodes_amount
        self.kube_nodes_instance_type = kube_nodes_instance_type
        self.timestamp = round(time.time() * 1000)
        self.working_dir = os.getenv('TF_WORKING_DIR')

    def configure_aws_cli(self):
        pass

    def create_vars_file(self):
        os.mkdir("/tmp/{}".format(self.timestamp))
        with open("/tmp/{}/tfvars.tf".format(self.timestamp), "w") as tfvars:
            tfvars.write("{} = {}\n".format("aws_region", self.aws_region))
            tfvars.write("{} = {}\n".format("aws_access_key", self.aws_access_key))
            tfvars.write("{} = {}\n".format("aws_secret_key", self.aws_secret_key))
            tfvars.write("{} = {}\n".format("clustername", self.clustername))
            tfvars.write("{} = {}\n".format("az1", self.az1))
            tfvars.write("{} = {}\n".format("az2", self.az2))
            tfvars.write("{} = {}\n".format("kube_nodes_amount", self.kube_nodes_amount))
            tfvars.write("{} = {}\n".format("kube_nodes_instance_type", self.kube_nodes_instance_type))

    def install_kube(self):
        process = Popen(['terraform', 'workspace', 'new', self.workspace], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        process.wait()
        self.create_vars_file()
        process = Popen(['terraform',
                         'apply',
                         '-var-file=/tmp/{}/tfvars.tf'.format(self.timestamp),
                         '-auto-approve',
                         self.working_dir], )
        stdout, stderr = process.communicate()
        process.wait(timeout=900)
        self.configure_awscli()




