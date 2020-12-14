import os
import time

import boto3

from common.shell import shell_run, create_dirs
# TODO: pass as parameters from POST request
from infra.cluster_service import *

class Terraform:
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
