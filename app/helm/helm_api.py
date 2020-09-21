import base64
import os
import sys
import tarfile
import time

import requests
import yaml

from common.shell import shell_run, create_dirs
from common.vault_api import Vault

SUPPORTED_VALUES = ("owner", "repo", "namespace")
DEV_BRANCHES = ("develop", "master")


class HelmDeployment:

    def __init__(self, logger, helm_values, k8s_cluster_conf, registries):
        self.logger = logger
        self.k8s_cluster_conf = k8s_cluster_conf
        self.registries = registries
        self.owner = helm_values['owner']
        self.repo = helm_values['repo']
        self.namespace = helm_values['namespace']
        self.image_tag = helm_values['image_tag']
        self.helm_version = helm_values.get("helm_version", f"1.0-{self.image_tag}")
        if 'env' not in helm_values:
            self.env = {}
        else:
            self.env = helm_values['env']

        # calculated properties

        self.timestamp = round(time.time() * 1000)
        self.target_path = f'{os.getcwd()}/state/pkg/{self.timestamp}'
        self.kube_conf_path = f'{os.getcwd()}/state/pkg/{self.timestamp}/kubeconfig'
        self.helm_dir = f'{self.target_path}'
        self.service_role = f"{self.owner}-{self.repo}-role"
        self.cluster_name = k8s_cluster_conf["cluster_name"]
        create_dirs(self.target_path)
        self.values = {k: v for (k, v) in helm_values.items() if k in SUPPORTED_VALUES}

    def untar_helm_gz(self, helm_tag_gz):
        self.logger.info(f'Untar helm_tar_gz is: {helm_tag_gz}')
        targz = tarfile.open(helm_tag_gz, "r:gz")
        targz.extractall(r"{}".format(self.target_path))

    def prepare_package(self):
        reg = self.registries.get("helm")
        if reg is None:
            return "No helm registry provided", 1
        helm_reg_url = f'https://{reg["username"]}:{reg["password"]}@{reg["path"]}'
        chart_path = f'{self.owner}/{self.repo}/{self.repo}-{self.helm_version}.tgz'
        url = f'{helm_reg_url}{chart_path}'
        r = requests.get(url)
        if r.status_code != 200:
            return f"Failed to find artifact in path {chart_path} or {reg['path']} not available", 1
        else:
            return r.content, 0

    def enrich_values_yaml(self):
        with open(f"{self.helm_dir}/{self.repo}/values.yaml") as default_values_yaml:
            actual_values = yaml.load(default_values_yaml, Loader=yaml.FullLoader)

        self.logger.info(f"Default values are: {actual_values}")

        # init traefik values if necessary:
        if "traefik" in actual_values and "dns_suffix" in self.k8s_cluster_conf:
            actual_values["traefik"]["dns_suffix"] = self.k8s_cluster_conf.get("dns_suffix")

        # docker token to put into image pull secret
        actual_values['dockerjsontoken'] = self.registries.get("docker", {}).get("dockerjsontoken", "")

        tolerations = self.__get_tolerations()
        if tolerations is not None:
            toleration = tolerations.get(self.repo, tolerations.get("default", "kubesystem"))
            toleration_val = {"key": "type", "value": toleration, "operator": "Equal", "effect": "NoSchedule"}
            actual_values['tolerations'] = [toleration_val]

        # set cluster name in 'env' per helm chart.
        # That should correspond to vault mount auth path (prefixed with 'kubernetes-')
        self.env['VAULT_MOUNT_POINT'] = f'kubernetes-{self.cluster_name}'
        self.env['CLUSTER_NAME'] = self.cluster_name

        # update values with ones posted in request
        actual_values.update(self.values)
        actual_values["env"] = self.env
        actual_values["service_account"] = f'{self.owner}-{self.repo}'
        # Set vault address into values.yaml if vault.addr key exists
        actual_values["vault"] = {"addr": os.getenv("VAULT_ADDR", "http://localhost:8200/"),
                                  "role": self.service_role,
                                  "jwtprovider": f'kubernetes-{self.cluster_name}'}
        actual_values["images"]["service"]["tag"] = self.image_tag
        self.logger.info(f"Env before writing: {actual_values}")
        path_to_values_yaml = f'{self.helm_dir}/spinless-values.yaml'
        with open(path_to_values_yaml, "w") as spinless_values_yaml:
            yaml.dump(actual_values, spinless_values_yaml, default_flow_style=False)
        return path_to_values_yaml, actual_values

    def install_package(self):
        """
        Runs helm install command according to the properties set up in object.
        :return: error_code of helm upgrade command and output of (err_code, output). If helm command failed,
        the output will also contain the helm command output log (including syserr)
        """
        pkg = f'{self.namespace}/{self.owner}/{self.repo}'
        result_output = list()
        result_output.append(f"{pkg}: Preparing package...")
        prepare_pkg_result, err = self.prepare_package()
        if err != 0:
            result_output.append(f"{pkg}: Preparing package failed: {prepare_pkg_result}")
            return err, result_output
        else:
            helm_tag_gz_path = f'{self.target_path}/{self.repo}.tgz'
            with open(helm_tag_gz_path, "wb") as helm_archive:
                helm_archive.write(prepare_pkg_result)
            self.untar_helm_gz(helm_tag_gz_path)

        result_output.append(f"{pkg}: Package ready")

        kubeconfig_base64 = self.k8s_cluster_conf.get("kube_config")
        if not kubeconfig_base64:
            result_output.append(f"{pkg}: WARNING: No kube ctx. Deploying to default cluster")
        else:
            with open(self.kube_conf_path, "w") as kubeconf_file:
                kubeconf_str = base64.standard_b64decode(kubeconfig_base64.encode("utf-8")).decode("utf-8")
                kubeconf_file.writelines(kubeconf_str)

        # set aws secrets and custom kubeconfig if all secrets are present, otherwise - default cloud wil be used
        env = {}
        if all(k in self.k8s_cluster_conf for k in ("aws_region", "aws_access_key", "aws_secret_key")):
            env = {"KUBECONFIG": self.kube_conf_path,
                   "AWS_DEFAULT_REGION": self.k8s_cluster_conf.get("aws_region"),
                   "AWS_ACCESS_KEY_ID": self.k8s_cluster_conf.get("aws_access_key"),
                   "AWS_SECRET_ACCESS_KEY": self.k8s_cluster_conf.get("aws_secret_key")
                   }

        values_path, values_content = self.enrich_values_yaml()

        if self.__requires_restart(env):
            # trigger pods restart for every redeploy
            values_content['timestamp'] = str(self.timestamp)

        # actually call helm install
        helm_install_cmd = f'helm upgrade -i {self.owner}-{self.repo} {self.helm_dir}/{self.repo} -f {values_path}  ' \
                           f'-n {self.namespace} --create-namespace --debug'

        result_output.append(f"{pkg}: Installing package: {helm_install_cmd}")
        err_code, cmd_output = shell_run(helm_install_cmd, env)
        cmd_output = map(lambda s: f"{pkg}: " + s, cmd_output)
        if err_code == 0:
            result_output.append(f"{pkg}: Release installed successfully ")
        else:
            result_output.append(f"{pkg}: Failed to install release. Details:")
            result_output.extend(cmd_output)
        return err_code, result_output

    def __get_tolerations(self):
        vault = Vault(self.logger)
        try:
            tolerations = vault.read(f"{vault.base_path}/tolerations/{self.cluster_name}")["data"]
            self.logger.info(f"Tolerations are: {tolerations}")
        except Exception as e:
            tolerations = None
            self.logger.info(f"Get tolerations Exception is: {e}")
        return tolerations

    def __requires_restart(self, env):
        if self.image_tag in DEV_BRANCHES:
            return True
        # get values from helm release
        code, output = shell_run(f"helm -n {self.namespace} get values {self.owner}-{self.repo} -o yaml",
                                 env=env,
                                 get_stream=True)
        # fresh installation - result doesn't matter
        if code != 0:
            return True
        try:
            chart_values = yaml.load(output, Loader=yaml.FullLoader)
            return chart_values['images']['service']['tag'] != self.image_tag
        except Exception as ex:
            return False
