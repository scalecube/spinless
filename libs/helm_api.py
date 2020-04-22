import os
import tarfile
import time

import requests
import yaml

from libs.shell import shell_await


class Helm:
    def __init__(self, logger, owner, repo, branch, posted_env, helm_version, registries=None,
                 k8s_cluster_conf=None, namespace="default", service_role=None, cluster_name=None):
        self.logger = logger
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.posted_env = posted_env
        self.helm_version = helm_version
        self.timestamp = round(time.time() * 1000)
        self.target_path = "/tmp/{}".format(self.timestamp)
        self.kube_conf_path = "/tmp/{}/{}".format(self.timestamp, "kubeconfig")
        self.helm_dir = "{}/{}".format(self.target_path, self.repo)
        self.namespace = namespace
        self.registries = registries
        self.k8s_cluster_conf = k8s_cluster_conf
        self.service_role = service_role
        self.cluster_name = cluster_name

    def untar_helm_gz(self, helm_tag_gz):
        self.logger.info("Untar helm_tar_gz is: {}".format(helm_tag_gz))
        targz = tarfile.open(helm_tag_gz, "r:gz")
        targz.extractall(r"{}".format(self.target_path))
        return

    def prepare_package(self):
        os.mkdir(self.target_path)
        reg = self.registries["helm"]
        helm_reg_url = 'https://{}:{}@{}'.format(
            reg['username'], reg['password'], reg['path'])
        chart_path = "{}/{}/{}-{}.tgz".format(self.owner, self.repo, self.repo, self.helm_version)
        url = "{}{}".format(helm_reg_url, chart_path)
        r = requests.get(url)
        if r.status_code != 200:
            return "Failed to find artifact in path {} or {} not available}".format(chart_path, reg['path']), 1
        else:
            return r.content, 0

    def enrich_values_yaml(self):
        with open("{}/values.yaml".format(self.helm_dir)) as default_values_yaml:
            default_values = yaml.load(default_values_yaml, Loader=yaml.FullLoader)
        env = default_values.get('env', {})
        self.logger.info("Default values are: {}".format(env))
        env.update(self.posted_env)
        default_values['env'] = env
        default_values['service_account'] = "{}-{}".format(self.owner, self.repo)

        # Set vault address inte values.yaml if vault.addr key exists
        default_values.get("vault", {})["addr"] = os.getenv("VAULT_ADDR", "http://localhost:8200/")
        default_values.get("vault")["role"] = self.service_role
        default_values.get("vault")["jwtprovider"] = "kubernetes-{}".format(self.cluster_name)

        self.logger.info("Env before writing: {}".format(default_values))
        path_to_values_yaml = "{}/spinless-values.yaml".format(self.helm_dir)
        with open(path_to_values_yaml, "w") as spinless_values_yaml:
            yaml.dump(default_values, spinless_values_yaml, default_flow_style=False)
        return path_to_values_yaml, default_values

    def install_package(self):
        yield "Preparing package...", None
        prepare_pkg_result, err = self.prepare_package()
        if err != 0:
            yield "Preparing package failed: {}".format(prepare_pkg_result), err
        else:
            helm_tag_gz_path = '{}/{}.tgz'.format(self.target_path, self.repo)
            with open(helm_tag_gz_path, "wb") as helm_archive:
                helm_archive.write(prepare_pkg_result)
            self.untar_helm_gz(helm_tag_gz_path)
        yield "Package ready", None
        kubeconfig = self.k8s_cluster_conf.get("kube_config")
        if not kubeconfig:
            yield "WARNING: No kube ctx. Deploying to default cluster", None
        else:
            with open(self.kube_conf_path, "w") as kubeconf_file:
                yaml.dump(eval(kubeconfig), kubeconf_file)

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
        kubectl = os.getenv("KUBECTL_PATH", "/usr/local/bin/kubectl")
        create_namespace_cmd = [kubectl, "create", "namespace", "{}".format(self.namespace)]
        shell_await(create_namespace_cmd, env)
        self.logger.info("Kubernetes namespace {} created".format(self.namespace))

        path_to_values_yaml, values_content = self.enrich_values_yaml()

        dockerjson = self.__dockerjson(values_content, self.registries)

        # actually call helm install
        helm_cmd = os.getenv('HELM_CMD', "/usr/local/bin/helm")
        helm_install_cmd = [helm_cmd, "upgrade", "--debug",
                            "--install", "--namespace",
                            self.namespace, "{}-{}-{}".format(self.owner, self.repo, self.namespace),
                            "-f", path_to_values_yaml,
                            self.helm_dir]
        if dockerjson:
            helm_install_cmd.append('--set')
            helm_install_cmd.append('dockerjsontoken={}'.format(dockerjson))
        yield "Installing package: {}".format(helm_install_cmd), None
        helm_install_res, stdout_iter = shell_await(helm_install_cmd, env, with_output=True)
        for s in stdout_iter:
            yield s, None
        yield "Helm command complete", helm_install_res

    def __dockerjson(self, valuesyaml, registries):
        if registries.get("docker"):
            result = registries.get("docker").get("dockerjsontoken", "")
        else:
            result = valuesyaml.get("dockerjsontoken", "")
        if not result or result == "":
            self.logger.warn(
                "Using default docker registry since didn't find dockerjson neither in values nor in registry data.")
        return result
