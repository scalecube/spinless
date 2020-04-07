import os
from subprocess import Popen, PIPE


class TF:
    def __init__(self, workspace):
        self.workspace = workspace
        self.working_dir = os.getenv('TF_WORKING_DIR')
        pass

    def install_kube(self, location, cloud, kube_version, ):
        process = Popen(['terraform', 'apply', self.working_dir], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()


