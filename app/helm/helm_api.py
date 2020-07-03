import base64
import os
import sys
import tarfile
import time

import requests
import yaml

from common.shell import shell_await
from common.vault_api import Vault


class HelmDeployment:

    def __init__(self, logger, k8s_cluster_conf, namespace, posted_values, owner, image_tag, repo, registries,
                 service_role, helm_version):

        self.prj_dir = os.path.dirname(sys.modules['__main__'].__file__)
        self.logger = logger
        self.owner = owner
        self.repo = repo
        self.posted_values = posted_values
        self.helm_version = helm_version
        self.timestamp = round(time.time() * 1000)
        self.target_path = f'{self.prj_dir}/state/pkg/{self.timestamp}'
        self.kube_conf_path = f'{self.prj_dir}/state/pkg/{self.timestamp}/kubeconfig'
        self.helm_dir = f'{self.target_path}'
        self.namespace = namespace
        self.registries = registries
        self.k8s_cluster_conf = k8s_cluster_conf
        self.service_role = service_role
        self.cluster_name = k8s_cluster_conf["cluster_name"]
        self.create_dir(self.target_path)
        self.image_tag = image_tag

    def create_dir(self, path):
        try:
            os.makedirs(path)
        except OSError:
            pass
        else:
            print("Successfully created the directory %s" % path)

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
            default_values = yaml.load(default_values_yaml, Loader=yaml.FullLoader)

        self.logger.info(f"Default values are: {default_values}")

        # init traefik values if necessary:
        if "traefik" in default_values and "dns_suffix" in self.k8s_cluster_conf:
            default_values["traefik"]["dns_suffix"] = self.k8s_cluster_conf.get("dns_suffix")

        # trigger pods restart any redeploy
        default_values['timestamp'] = str(self.timestamp)

        # docker token to put into image pull secret
        default_values['dockerjsontoken'] = self.registries.get("docker", {}).get("dockerjsontoken", "")

        # set cluster name in 'env' per helm chart.
        # That should correspond to vault mount auth path (prefixed with 'kubernetes-')
        self.posted_values.get('env', {})['VAULT_MOUNT_POINT'] = f'kubernetes-{self.cluster_name}'
        self.posted_values.get('env')['CLUSTER_NAME'] = self.cluster_name

        # update values with ones posted in request
        default_values.update(self.posted_values)
        default_values["service_account"] = f'{self.owner}-{self.repo}'
        # Set vault address into values.yaml if vault.addr key exists
        default_values["vault"] = {"addr": os.getenv("VAULT_ADDR", "http://localhost:8200/"),
                                   "role": self.service_role,
                                   "jwtprovider": f'kubernetes-{self.cluster_name}'}
        default_values["images"]["service"]["tag"] = self.image_tag
        self.logger.info(f"Env before writing: {default_values}")
        path_to_values_yaml = f'{self.helm_dir}/spinless-values.yaml'
        with open(path_to_values_yaml, "w") as spinless_values_yaml:
            yaml.dump(default_values, spinless_values_yaml, default_flow_style=False)
        return path_to_values_yaml, default_values

    def get_tolerations(self):
        vault = Vault(self.logger)
        try:
            tolerations = vault.read(f"{vault.vault_secrets_path}/tolerations/{self.cluster_name}")["data"]
            self.logger.info(f"Tolerations are: {tolerations}")
        except Exception as e:
            tolerations = False
            self.logger.info(f"Get tolerations Exception is: {e}")
        return tolerations

    def install_package(self):
        yield "Preparing package...", None
        prepare_pkg_result, err = self.prepare_package()
        if err != 0:
            yield f"Preparing package failed: {prepare_pkg_result}", err
        else:
            helm_tag_gz_path = f'{self.target_path}/{self.repo}.tgz'
            with open(helm_tag_gz_path, "wb") as helm_archive:
                helm_archive.write(prepare_pkg_result)
            self.untar_helm_gz(helm_tag_gz_path)
        yield "Package ready", None
        kubeconfig_base64 = self.k8s_cluster_conf.get("kube_config")
        if not kubeconfig_base64:
            yield "WARNING: No kube ctx. Deploying to default cluster", None
        else:
            with open(self.kube_conf_path, "w") as kubeconf_file:
                kubeconf_str = base64.standard_b64decode(kubeconfig_base64.encode("utf-8")).decode("utf-8")
                kubeconf_file.writelines(kubeconf_str)

        # set aws secrets and custom kubeconfig if all secrets are present, otherwise - default cloud wil be used
        if all(k in self.k8s_cluster_conf for k in ("aws_region", "aws_access_key", "aws_secret_key")):
            env = {"KUBECONFIG": self.kube_conf_path,
                   "AWS_DEFAULT_REGION": self.k8s_cluster_conf.get("aws_region"),
                   "AWS_ACCESS_KEY_ID": self.k8s_cluster_conf.get("aws_access_key"),
                   "AWS_SECRET_ACCESS_KEY": self.k8s_cluster_conf.get("aws_secret_key")
                   }
        else:
            env = {}

        # create k8 namespace if necessary
        kubectl = self.get_kubectl_cmd()

        create_namespace_cmd = [kubectl, "create", "namespace", f"{self.namespace}"]
        shell_await(create_namespace_cmd, env)
        self.logger.info(f"Kubernetes namespace {self.namespace} created")

        path_to_values_yaml, values_content = self.enrich_values_yaml()

        # actually call helm install
        helm_install_cmd = ['helm', "upgrade",
                            f'{self.owner}-{self.repo}',
                            f'{self.helm_dir}/{self.repo}', "--force",
                            "--debug", "--install", "--namespace", self.namespace,
                            "-f", path_to_values_yaml,
                            ]
        self.logger.info("Adding tolerations")
        # Tolerations
        # TODO: tolerations class and array of tolerations
        tolerations = self.get_tolerations()
        if tolerations:
            toleration_val = tolerations.get(self.repo, tolerations.get("default"))
            helm_install_cmd.append('--set')
            helm_install_cmd.append('tolerations[0].key=type')
            helm_install_cmd.append('--set')
            helm_install_cmd.append(f'tolerations[0].value={toleration_val}')
            helm_install_cmd.append('--set')
            helm_install_cmd.append('tolerations[0].operator=Equal')
            helm_install_cmd.append('--set')
            helm_install_cmd.append('tolerations[0].effect=NoSchedule')

        yield f"Installing package: {helm_install_cmd}", None
        helm_install_res, stdout_iter = shell_await(helm_install_cmd, env, with_output=True)
        if helm_install_res != 0:
            for s in stdout_iter:
                yield s, None
        yield f'Helm command complete with error code={helm_install_res}', helm_install_res

    def get_kubectl_cmd(self):
        kubectl = os.getenv("KUBECTL_PATH", "/usr/local/bin/kubectl")
        if os.name == 'nt':
            kubectl = "kubectl"
        return kubectl
