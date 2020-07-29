import base64
import json
import os
import time

import boto3
from jinja2 import Environment, FileSystemLoader

from common.kube_api import KctxApi
from common.shell import shell_run, create_dirs
from common.vault_api import Vault

# TODO: pass as parameters from POST request
INFRA_TEMPLATES_ROOT = "infra/templates"
DYNAMO_LOCK_TABLE = "terraform-lock"
CONFIG_ENVIRONMENT = "develop"
CONFIG_VERSION = "v0.2"
# TEST_CONFIG_REPOSITORY = "exberry-io/terraform-config-simple-aws"
CONFIG_REPOSITORY = "exberry-io/terraform-eks-exberry-tenant"

KUBECONF_FILE = "kubeconfig"
BACKEND_FILE = 'backend.tf'


class Terraform:
    def __init__(self, logger=None, cluster_name=None, aws_creds=None, tf_vars=None, dns_suffix=None, action="UNKNOWN"):
        self.logger = logger
        self.cluster_name = cluster_name
        self.aws_creds = aws_creds
        self.tf_vars = tf_vars
        self.dns_suffix = dns_suffix

        # calculated props
        timestamp = round(time.time() * 1000)
        self.work_dir = f'{os.getcwd()}/state/clusters/{action}-{cluster_name}-{timestamp}'
        create_dirs(self.work_dir)
        self.kube_config_file_path = f"{self.work_dir}/{KUBECONF_FILE}"
        self.templates = Environment(loader=FileSystemLoader("infra/templates"), trim_blocks=True)
        self.kctx_api = KctxApi(logger)

        # cluster state properties
        # TODO: pass as parameters from POST request
        self.tf_dynamodb_table = DYNAMO_LOCK_TABLE  # dynamodb table used to lock states
        self.env = CONFIG_ENVIRONMENT  # (dev/preprod/prod)
        self.tf_repository = CONFIG_REPOSITORY  # github repository with tf module to use
        self.tf_repository_version = CONFIG_VERSION  # version of release of github repo
        self.tf_s3_bucket = f'exberry-terraform-states-{self.env}'
        self.s3_env_path = f"environments/{self.cluster_name}"
        self.s3 = boto3.client('s3',
                               region_name=aws_creds["aws_region"],
                               aws_access_key_id=aws_creds["aws_access_key"],
                               aws_secret_access_key=aws_creds["aws_secret_key"],
                               )

    def create_cluster(self):
        working_with_existing_cluster = False
        self.logger.info(f"Started to create cluster in directory {self.work_dir}")
        # generate tf configuration files (using mapping between cluster type to github repo for tf files)
        self.__generate_backend_tf()

        # generate tf credentials (aws credentials and actually cluster configs)
        yield "RUNNING: Creating Terraform vars", None
        aws_vars_path, aws_vars = self._generate_aws_variables()

        cluster_vars_path, cluster_vars = self.__read_environment()
        if cluster_vars_path and cluster_vars:
            yield f"Cluster {self.cluster_name} exists, using its state and variables", None
            working_with_existing_cluster = True
        else:
            # cluster_vars_path, cluster_vars = self.__generate_cluster_variables()
            cluster_vars_path, cluster_vars = self.__generate_cluster_variables_real()
            yield "New cluster is being created. Generated tf vars for that", None

        self.__generate_tf_configs(aws_vars + cluster_vars)

        # Terraform init
        _cmd_init = f"terraform init"
        yield "RUNNING: Initializing terraform...", None
        # Attention to "cwd=" that's important to work in same directory (/tmp/...)
        err, outp = shell_run(_cmd_init, cwd=self.work_dir, timeout=300)
        for s in outp:
            yield f"Terraform init: {s}", None
        if err != 0:
            yield f"FAILED: Failed to init terraform in dir {self.work_dir}", err
        else:
            yield "RUNNING: Terraform init complete", None

        # TODO: this is workaround(?). need to copy variables.tf to working dir
        _cmd_copy_variables = f"cp {self.work_dir}/.terraform/modules/{self.cluster_name}/variables.tf {self.work_dir}/"
        shell_run(_cmd_copy_variables)

        # Terraform apply
        _cmd_apply = f"terraform apply -var-file={aws_vars_path} -var-file={cluster_vars_path} -auto-approve"
        yield f"RUNNING: Actually creating cluster. This may take time... {_cmd_apply}", None
        err_code_apply, outp = shell_run(_cmd_apply, cwd=self.work_dir, timeout=900)
        for s in outp:
            self.logger.info(s)
            yield f"Terraform apply: {s}", None
        self.logger.info(f"Terraform finished cluster creation. Errcode: {err_code_apply}")
        if err_code_apply != 0:
            yield "FAILED: Failed to create cluster", err_code_apply
        else:
            yield "RUNNING: Terraform has successfully created cluster", None

        for msg, status in self.__cluster_post_setup():
            if status is not None:
                if status == 0:
                    yield msg, None
                    break
                else:
                    yield msg, status
            yield msg, status

        if not working_with_existing_cluster:
            yield "Saving cluster parameters to S3...", None
            result = self.__save_cluster_to_s3(cluster_vars_path)
            if result:
                yield "Saving cluster parameters to S3: OK", None
            else:
                yield "Saving cluster parameters to S3: FAIL", None
        else:
            yield "Working with existing cluster, no variables saved to S3", None
        yield "success", 0

    def destroy_cluster(self):
        self.logger.info(f"Started to DESTROY cluster {self.cluster_name}  in directory {self.work_dir}")
        # generate tf backend
        self.__generate_backend_tf()

        cluster_vars_path, cluster_vars = self.__read_environment()
        if not cluster_vars_path or not cluster_vars:
            yield f"FAILED: cluster {self.env}/{self.cluster_name} does not exist", 1

        yield "RUNNING: Creating AWS vars", None
        aws_vars_path, aws_vars = self._generate_aws_variables()

        self.__generate_tf_configs(aws_vars + cluster_vars)

        # Terraform init
        _cmd_init = f"terraform init"
        yield "RUNNING: Initializing terraform...", None
        # Attention to "cwd=" that's important to work in same directory (/tmp/...)
        err, outp = shell_run(_cmd_init, cwd=self.work_dir, timeout=300)
        for s in outp:
            yield f"Terraform init: {s}", None
        if err != 0:
            yield f"FAILED: Failed to init terraform in dir {self.work_dir}", err
        else:
            yield "RUNNING: Terraform init complete", None

        _cmd_copy_variables = f"cp {self.work_dir}/.terraform/modules/{self.cluster_name}/variables.tf {self.work_dir}/"
        shell_run(_cmd_copy_variables)

        _cmd_destroy = f"terraform destroy -var-file={aws_vars_path} -var-file={cluster_vars_path} -auto-approve"
        yield f"RUNNING: Actually DESTROYING cluster. This may take time... {_cmd_destroy}", None
        err_code_destroy, outp = shell_run(_cmd_destroy, cwd=self.work_dir, timeout=900)
        for s in outp:
            self.logger.info(s)
            yield f"Terraform destroy: {s}", None
        self.logger.info(f"Terraform destroy complete. Errcode: {err_code_destroy}")
        if err_code_destroy != 0:
            yield "FAILED: Failed to destroy cluster", err_code_destroy
        else:
            yield "RUNNING: Terraform has successfully destroyed cluster", None

        for msg, status in self.__cluster_post_destroy():
            yield msg, status
            if status is not None:
                break

        yield "Clearing cluster parameters from S3...", None
        result = self.__delete_cluster_from_s3()
        if result:
            yield "Delete cluster parameters from S3: OK", None
        else:
            yield "Delete cluster parameters from S3: FAIL", None

        yield "success", 0

    def _generate_aws_variables(self):
        """
        generate file containing aws credentials (aws.tfvars)
        :return: pair of filename that was generated and actual dictionary of its content
        """
        f_name = f"{self.work_dir}/aws.tfvars"
        with open(f_name, "w") as aws_vars:
            aws_vars.write(f'aws_region = "{self.aws_creds["aws_region"]}"\n')
            aws_vars.write(f'aws_access_key = "{self.aws_creds["aws_access_key"]}"\n')
            aws_vars.write(f'aws_secret_key = "{self.aws_creds["aws_secret_key"]}"\n')
        return f_name, list(self.aws_creds.keys())

    def __generate_cluster_variables_real(self):
        """
        generate file containing cluster variables names credentials (tfvars.tfvars)
        :return: pair of filename that was generated and actual dictionary of its content
        """
        f_name = f"{self.work_dir}/cluster.tfvars"
        vars = self.tf_vars
        vars["nodePools"] = json.dumps(vars["properties"]["eks"]["nodePools"])
        with open(f_name, "w") as tfvars:
            gen_template = self.templates.get_template('template_tfvars.tf').render(variables=vars)
            tfvars.write(gen_template)

        vars.pop("properties")
        vars["cluster-name"] = vars.pop("cluster_name")
        return f_name, list(vars.keys())

    # Test with this configuration, not the real one
    def __generate_test_cluster_variables(self):
        f_name = f"{self.work_dir}/cluster.tfvars"
        tf_vars = {"instance_type": "t3.micro"}
        with open(f_name, "w") as tfvars:
            gen_template = self.templates.get_template('template_tfvars-test.tf').render(
                variables=tf_vars)
            tfvars.write(gen_template)
        return f_name, list(tf_vars.keys())

    def __read_environment(self):
        """
        Checks if terraform.state exists for env/cluster_name.
        Then reads tf vars from s3 bucket (according to env/cluster_name)
        :return: path to downloaded tfvars, and tfvars keys (var names)
        """
        try:
            # check if state exists:
            if self._s3_key_exists(f"states/{self.cluster_name}/terraform.tfstate") is None:
                return False, False
            # download variables (if fails - return False
            f_name = f'{self.work_dir}/cluster.tfvars'
            self.s3.download_file(self.tf_s3_bucket, f"{self.s3_env_path}/cluster.tfvars", f_name)
            # extract keys from var file
            var_keys = self.__read_keys_from_vars_file(f_name)
            if var_keys is None:
                return False, False
            return f_name, var_keys
        except Exception as e:
            self.logger.error(e)
            return False, False

    def _s3_key_exists(self, key):
        """
        return the key's size if it exist, else None
        """
        response = self.s3.list_objects_v2(
            Bucket=self.tf_s3_bucket,
            Prefix=key,
        )
        for obj in response.get('Contents', []):
            if obj['Key'] == key:
                return obj['Size']

    def __generate_backend_tf(self):
        f_name = f"{self.work_dir}/{BACKEND_FILE}"
        with open(f_name, "w") as file:
            gen_template = self.templates.get_template('template_backend.tf').render(
                cluster_name=self.cluster_name,
                bucket=self.tf_s3_bucket,
                region=self.aws_creds["aws_region"],
                access_key=self.aws_creds["aws_access_key"],
                secret_key=self.aws_creds["aws_secret_key"],
                dynamodb_table=self.tf_dynamodb_table)
            file.write(gen_template)
        return f_name

    def __generate_tf_configs(self, all_variables):
        f_name = f"{self.work_dir}/main.tf"
        with open(f_name, "w") as file:
            gen_template = self.templates.get_template('template_main.tf').render(
                module_name=self.cluster_name,
                repository=self.tf_repository,
                version=self.tf_repository_version,
                variables=all_variables)
            file.write(gen_template)
        return f_name

    def __generate_configmap(self):
        client = boto3.client('iam',
                              region_name=self.aws_creds["aws_region"],
                              aws_access_key_id=self.aws_creds["aws_access_key"],
                              aws_secret_access_key=self.aws_creds["aws_secret_key"],
                              )
        role_arn = client.get_role(RoleName=f'eks-node-role-{self.cluster_name}')['Role']['Arn']
        f_name = f"{self.work_dir}/nodes_cm.yaml"
        with open(f_name, "w") as nodes_cm:
            gen_template = self.templates.get_template('nodes_cm.j2').render(aws_iam_role_eksnode_arn=role_arn)
            nodes_cm.write(gen_template)
        return f_name

    def __apply_node_auth_configmap(self, kube_env):
        self.__generate_configmap()
        kube_cmd = f"kubectl apply -f {self.work_dir}/nodes_cm.yaml"
        res, outp = shell_run(kube_cmd, env=kube_env)
        if res != 0:
            for s in outp:
                self.logger.info(s)
            return res, "Failed to create nodes_cm"
        return res, outp

    def __cluster_post_setup(self):
        # Generate cluster config
        yield "RUNNING: Generating kubernetes cluster config...", None

        kube_conf_str, err = KctxApi.generate_aws_kube_config(cluster_name=self.cluster_name,
                                                              aws_region=self.aws_creds["aws_region"],
                                                              aws_access_key=self.aws_creds["aws_access_key"],
                                                              aws_secret_key=self.aws_creds["aws_secret_key"],
                                                              conf_path=self.kube_config_file_path,
                                                              templates_root=INFRA_TEMPLATES_ROOT
                                                              )
        if err == 0:
            yield "RUNNING: Kubernetes config generated successfully", None
        else:
            yield "ERROR: Failed to create kubernetes config", err

        kube_env = {"KUBECONFIG": self.kube_config_file_path,
                    "AWS_DEFAULT_REGION": self.aws_creds["aws_region"],
                    "AWS_ACCESS_KEY_ID": self.aws_creds["aws_access_key"],
                    "AWS_SECRET_ACCESS_KEY": self.aws_creds["aws_secret_key"]
                    }
        # Apply node auth confmap
        yield "RUNNING: Applying node auth configmap...", None
        auth_conf_map_result, msg = self.__apply_node_auth_configmap(kube_env)
        if auth_conf_map_result != 0:
            yield "FAILED: Failed to apply node config map...", auth_conf_map_result
        else:
            yield "SUCCESS: Cluster creation and conf setup complete", None

        # Provision Vault
        vault_prov_res, msg = self.kctx_api.provision_vault(self.cluster_name, self.work_dir, kube_env,
                                                            templates_root=INFRA_TEMPLATES_ROOT)
        if vault_prov_res != 0:
            yield f"FAILED: Failed setup vault account in new cluster. Aborting: {msg}", vault_prov_res
        yield "Vault provisioning complete", None

        # Set up storage
        storage_res, msg = self.kctx_api.setup_storage(kube_env, self.work_dir, templates_root=INFRA_TEMPLATES_ROOT)
        if storage_res != 0:
            yield "FAILED: Failed to setup storage volume. Aborting: {}".format(msg), storage_res
        yield "Storage volume set up successfully.", None

        #  Setup cluster autoscaler
        ca, msg = self.kctx_api.setup_ca(kube_env, self.cluster_name, self.aws_creds["aws_region"])
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
            yield f"FAILED: Failed to setup metrics. Aborting: {msg}", None  # TODO: res
        yield "Metrics installed successfully.", None

        # If deployment was successful, save kubernetes context to vault
        kube_conf_base64 = base64.standard_b64encode(kube_conf_str.encode("utf-8")).decode("utf-8")
        self.kctx_api.save_aws_context(aws_access_key=self.aws_creds["aws_access_key"],
                                       aws_secret_key=self.aws_creds["aws_secret_key"],
                                       aws_region=self.aws_creds["aws_region"],
                                       kube_cfg_base64=kube_conf_base64,
                                       cluster_name=self.cluster_name,
                                       dns_suffix=self.dns_suffix)
        yield "Saved cluster config.", None

    def __save_cluster_to_s3(self, cluster_vars_path):
        cluster_info_path = f"{self.work_dir}/cluster_info.yaml"
        with open(cluster_info_path, "w") as file:
            gen_template = self.templates.get_template('template_cluster_info.yaml').render(
                env=self.env,
                cluster_name=self.cluster_name,
                github_module_ref=self.tf_repository,
                github_module_version=self.tf_repository_version)
            file.write(gen_template)
        try:
            self.s3.upload_file(cluster_vars_path, self.tf_s3_bucket, f"{self.s3_env_path}/cluster.tfvars")
            self.s3.upload_file(cluster_info_path, self.tf_s3_bucket, f"{self.s3_env_path}/cluster_info.yaml")
        except Exception as e:
            self.logger.error(e)
            return False
        return True

    def __delete_cluster_from_s3(self):
        try:
            self.s3.delete_object(Bucket=self.tf_s3_bucket, Key=f"{self.s3_env_path}")
            self.s3.delete_object(Bucket=self.tf_s3_bucket, Key=f"states/{self.cluster_name}")
        except Exception as e:
            self.logger.error(e)
            return False
        return True

    def __read_keys_from_vars_file(self, file):
        try:
            with open(file, 'r') as reader:
                return list(map(lambda l: l.split(" = ")[0], reader.readlines()))
        except Exception as ex:
            self.logger.warn(f"Error while getting keys from variables file: {ex}")
            return None

    def __cluster_post_destroy(self):
        # Generate cluster config
        yield "RUNNING: Performing cluster post-destroy actions...", None

        # Disable vault mount point
        res, msg = Vault(self.logger).disable_vault_mount_point(self.cluster_name)
        if res != 0:
            yield f"FAILED: Failed to disable vault mount point", res
        yield f"Disabled Vault mount point for {self.cluster_name}", None

        # If deployment was successful, save kubernetes context to vault
        self.kctx_api.delete_kubernetes_context(self.cluster_name)
        yield "Cleared cluster config.", None
