import base64
import os
import shlex
import time

import boto3
from jinja2 import Environment, FileSystemLoader

from common.shell import shell_await
from common.vault_api import Vault

VALUT_AUTH = "vault-auth"

STATUS_OK_ = {"status": "OK"}
DEFAULT_K8S_CTX_ID = "default"
K8S_CTX_PATH = "kctx"
HELM = os.getenv('HELM_CMD', "/usr/local/bin/helm")


class KctxApi:
    def __init__(self, logger):
        self.vault = Vault(logger)
        self.logger = logger

    def save_kubernetes_context(self, ctx_data):
        if not ctx_data:
            self.logger.error("No kube ctx data provided")
            return {"error": "No kube ctx data provided"}
        if "name" not in ctx_data:
            self.logger.error("Mandatory fields not provided \"name\"")
            return {"error": "Mandatory fields not provided \"name\""}
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K8S_CTX_PATH, ctx_data["name"])
        attempts = 0
        while attempts < 3:
            try:
                self.logger.info("Saving kube ctx data into path: {}".format(kctx_path))
                self.vault.write(kctx_path, **ctx_data)
                return STATUS_OK_
            except Exception as e:
                self.logger.info("Failed to write secret to path {}, {}; attempt = {}".format(kctx_path, e, attempts))
                attempts += 1
        return {"error": "Failed to write secret"}

    def save_aws_context(self, aws_access_key, aws_secret_key, aws_region, kube_cfg_base64, cluster_name, dns_suffix):
        secret = {"aws_secret_key": aws_secret_key, "aws_access_key": aws_access_key, "aws_region": aws_region,
                  "kube_config": kube_cfg_base64, "name": cluster_name, "dns_suffix": dns_suffix}
        return self.save_kubernetes_context(secret)

    def get_kubernetes_context(self, cluster_name):
        self.logger.info("Getting kube context")
        if not cluster_name:
            self.logger.warn("Kube ctx \"name\" is empty, using \"default\"")
            cluster_name = DEFAULT_K8S_CTX_ID
        kctx_path = f'{self.vault.vault_secrets_path}/{K8S_CTX_PATH}/{cluster_name}'
        try:
            kctx_secret = self.vault.read(kctx_path)
            if not kctx_secret or not kctx_secret["data"]:
                return f'No such kctx: {cluster_name}', 1
            result = kctx_secret["data"]
            result["cluster_name"] = cluster_name
            return result, 0
        except Exception as e:
            return f'Failed to read secret {kctx_path}: {e}', 1

    def get_clusters_list(self):
        self.logger.info("Listing all clusters")
        clusters_path = f'{self.vault.vault_secrets_path}/{K8S_CTX_PATH}'
        return self.vault.list(clusters_path)

    def delete_kubernetes_context(self, cluster_name):
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K8S_CTX_PATH, cluster_name)
        try:
            self.vault.delete(kctx_path)
            return 0, "Deleted kcts successfully"
        except Exception as e:
            self.logger.error("Failed to delete secret from path {}, {}".format(kctx_path, e))
            return 1, "Failed to delete secret from storage"

    @staticmethod
    def generate_aws_kube_config(cluster_name, aws_region,
                                 aws_access_key, aws_secret_key, conf_path):
        try:
            # Set up the client
            s = boto3.Session(region_name=aws_region,
                              aws_access_key_id=aws_access_key,
                              aws_secret_access_key=aws_secret_key
                              )
            eks = s.client("eks")

            # get cluster details
            cluster = eks.describe_cluster(name=cluster_name)
            cluster_cert = cluster["cluster"]["certificateAuthority"]["data"]
            cluster_ep = cluster["cluster"]["endpoint"]

            # build the cluster config and write to file
            with open(conf_path, "w") as kube_conf:
                j2_env = Environment(loader=FileSystemLoader("app/infra/templates"),
                                     trim_blocks=True)
                gen_template = j2_env.get_template('cluster_config.j2').render(
                    cert_authority=str(cluster_cert),
                    cluster_endpoint=str(cluster_ep),
                    cluster_name=cluster_name)
                kube_conf.write(gen_template)
        except Exception as ex:
            return str(ex), 1
        return gen_template, 0

    def provision_vault(self, cluster_name, root_path, kube_env):
        try:
            os.makedirs(root_path, exist_ok=True)
            sa_path = "{}/vault_sa.yaml".format(root_path)
            with open(sa_path, "w") as vault_sa:
                j2_env = Environment(loader=FileSystemLoader("app/infra/templates"),
                                     trim_blocks=True)
                gen_template = j2_env.get_template('vault_sa.j2').render(vault_service_account_name=VALUT_AUTH)
                vault_sa.write(gen_template)
            create_roles_cmd = ['kubectl', "create", "-f", sa_path]
            # set aws secrets and custom kubeconfig if all secrets are present, otherwise - default cloud will be used

            res, outp = shell_await(create_roles_cmd, env=kube_env, with_output=True)
            for s in outp:
                self.logger.info(s)
            if res != 0:
                self.logger.warn("Failed to create service role in newly created cluster")
            else:
                self.logger.info("SA for Vault created in newly created cluster.")
            code, msg = self.__configure_kubernetes_mountpoint(kube_env, cluster_name)
            return 0, "Vault integration complete with status: {}:{} ".format(code, msg)
        except Exception as ex:
            self.logger.error("Error provisioning vault: {}".format(str(ex)))
            return 1, str(ex)

    def __configure_kubernetes_mountpoint(self, env, cluster_name):
        # getting reviewer token
        tok_rew_cmd = shlex.split("kubectl -n default get secret vault-auth -o go-template='{{ .data.token }}'")
        res, outp = shell_await(tok_rew_cmd, env=env, with_output=True)
        if res != 0:
            for s in outp:
                self.logger.info(s)
            return res, "Failed to get vault-auth jwt token"
        reviewer_jwt = base64.standard_b64decode(outp.__next__()).decode("utf-8")

        # get kube CA
        kube_ca_cmd = shlex.split(
            "kubectl -n default config view --raw --minify --flatten -o jsonpath='{.clusters[].cluster.certificate-authority-data}'")
        res, outp = shell_await(kube_ca_cmd, env=env, with_output=True)
        if res != 0:
            for s in outp:
                self.logger.info(s)
            return res, "Failed to get kube ca"
        kube_ca = base64.standard_b64decode(outp.__next__()).decode("utf-8")

        # get kube server
        kube_server_cmd = shlex.split(
            "kubectl -n default config view --raw --minify --flatten -o jsonpath='{.clusters[].cluster.server}'")
        res, outp = shell_await(kube_server_cmd, env=env, with_output=True)
        if res != 0:
            for s in outp:
                self.logger.info(s)
            return res, "Failed to get kube ca"
        kube_server = outp.__next__()

        # Create vault mount point
        return self.vault.enable_k8_auth(cluster_name, reviewer_jwt, kube_ca, kube_server)

    def setup_storage(self, kube_env, tmp_root_path):
        """
        Creates aws storage in eks cluster

        :param kube_env: env to use for kubernetes communication
        :param tmp_root_path: tmp path to store tmp files
        :return: err code (0 if success), message
        """
        res, outp = KctxApi.__install_to_kube(
            "aws-storage",
            {"app": "exchange"},
            kube_env, tmp_root_path)
        for out in outp:
            self.logger.info(out)
        return 0, "Volume creation complete. Result: {}".format(res)

    def execute_command(self, command, kube_env):
        cmd = shlex.split(command)
        res, logs = shell_await(cmd, env=kube_env, with_output=True)
        for l in logs:
            self.logger.info(l)
        return res, logs

    def setup_ca(self, kube_env, cluster_name, region):
        command = "helm repo add stable https://kubernetes-charts.storage.googleapis.com/"
        self.execute_command(command, kube_env)

        command = "kubectl create namespace cluster-autoscaler"
        self.execute_command(command, kube_env)

        command = f'helm install cluster-autoscaler stable/cluster-autoscaler ' \
                  f'--set autoDiscovery.clusterName={cluster_name} ' \
                  f'--set awsRegion={region} ' \
                  f'--set tolerations[0].key=type ' \
                  f'--set tolerations[0].value=kubsystem ' \
                  f'--set tolerations[0].operator=Equal ' \
                  f'--set tolerations[0].effect=NoSchedule ' \
                  f'--set rbac.create=true ' \
                  f'--set rbac.serviceAccount.name=cluster-autoscaler ' \
                  f'--namespace cluster-autoscaler'
        return self.execute_command(command, kube_env)

    def setup_traefik(self, kube_env):
        """
        Setup traefik plugin in created cluster

        :param kube_env: env to use for kubernetes communication
        :param tmp_root_path: tmp path to store tmp files
        :return: err code (0 if success), message
        """
        command = f'{HELM} repo add traefik https://containous.github.io/traefik-helm-chart'
        self.execute_command(command, kube_env)

        command = f'{HELM} repo update'
        self.execute_command(command, kube_env)

        command = "kubectl create namespace traefik"
        self.execute_command(command, kube_env)

        command = f'{HELM} upgrade --install traefik traefik/traefik ' \
                  f'--set service.type=NodePort ' \
                  f'--set ports.web.nodePort=30003 ' \
                  f'--set tolerations[0].key=type ' \
                  f'--set tolerations[0].value=kubsystem ' \
                  f'--set tolerations[0].operator=Equal ' \
                  f'--set tolerations[0].effect=NoSchedule ' \
                  f'--namespace traefik'
        return self.execute_command(command, kube_env)

    def setup_metrics(self, kube_env):
        """
        Install Metrics API in created cluster

        :param kube_env: env to use for kubernetes communication
        :param tmp_root_path: tmp path to store tmp files
        :return: err code (0 if success), message
        """
        command = "kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.3.6/components.yaml --namespace=kube-system"
        self.execute_command(command, kube_env)

        command = """kubectl patch deployment metrics-server -n kube-system --type=json -p='[{"op":"add", "path":"/spec/template/spec/tolerations", "value":[{"key":"type", "value":"kubsystem", "operator":"Equal", "effect":"NoSchedule"}]}]'"""
        self.execute_command(command, kube_env)

        command = """kubectl patch deployment coredns -n kube-system --type=json -p='[{"op":"add", "path":"/spec/template/spec/tolerations/-", "value":{"key":"type", "value":"kubsystem", "operator":"Equal", "effect":"NoSchedule"}}]'"""
        return self.execute_command(command, kube_env)

    @classmethod
    def __install_to_kube(cls, template_name, params, kube_env, root_path):
        """
        :param cls: class
        :param template_name: name without ".j2"
        :param params: data to pass to template
        :param kube_env:
        :param root_path:
        :param logger:
        :return:  errcode, msg
        """
        f_path = "{}/{}.yaml".format(root_path, template_name)
        with open(f_path, "w") as f:
            j2_env = Environment(loader=FileSystemLoader("app/infra/templates"),
                                 trim_blocks=True)
            gen_template = j2_env.get_template('{}.j2'.format(template_name)).render(**params)
            f.write(gen_template)
        cmd = shlex.split("kubectl apply -f {}".format(f_path))
        return shell_await(cmd, env=kube_env, with_output=True)

    def __write_and_get_kube_env(self, cluster_name):
        try:
            kctx, err = self.get_kubernetes_context(cluster_name)
            if err != 0:
                return f"Can't get cluster {cluster_name}", 1
            root_path = f"/tmp/{round(time.time() * 1000)}"
            os.makedirs(root_path, exist_ok=True)
            kube_config_file_path = f"{root_path}/kubeconf"

            kube_conf_base64 = kctx["kube_config"]
            with open(kube_config_file_path, "w") as kubeconf_file:
                kubeconf_str = base64.standard_b64decode(kube_conf_base64.encode("utf-8")).decode("utf-8")
                kubeconf_file.writelines(kubeconf_str)

            kube_env = {"KUBECONFIG": kube_config_file_path,
                        "AWS_DEFAULT_REGION": kctx["aws_region"],
                        "AWS_ACCESS_KEY_ID": kctx["aws_access_key"],
                        "AWS_SECRET_ACCESS_KEY": kctx["aws_secret_key"]}
            return kube_env, 0
        except Exception as e:
            return f"Failed to get kube env: {e}", 1

    def get_ns(self, cluster_name):
        '''
        Get current namespaces in cluster
        :param cluster_name:
        :return: list of namespaces iterable and error code (0 if success) or Error message and err code (if error)
        '''
        kube_env, err = self.__write_and_get_kube_env(cluster_name)
        if err != 0:
            return kube_env, 1
        cmd = shlex.split("kubectl get ns --output=name")
        result, output = shell_await(cmd, env=kube_env, with_output=True)
        if result != 0:
            for l in output:
                self.logger.error(l)
            return "Failed to 'kubectl get ns' ", 1
        return list(map(lambda ns: str.replace(ns, "namespace", cluster_name), output)), 0

    def delete_ns(self, cluster_name, ns):
        '''
        :param cluster_name:
        :param ns: name of namespace to be deleted
        :return: name of deleted namespace + 0 if success. Otherwise - error msg and error code
        '''
        kube_env, err = self.__write_and_get_kube_env(cluster_name)
        if err != 0:
            return kube_env, 1
        cmd = shlex.split(f"kubectl delete ns {ns}")
        result, output = shell_await(cmd, env=kube_env, with_output=False)
        if result != 0:
            return f"Failed to 'kubectl delete ns {ns}' ", 1
        return ns, 0
