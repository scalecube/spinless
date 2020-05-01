import base64
import os
import shlex

import boto3
from jinja2 import Environment, FileSystemLoader

from libs.shell import shell_await

VALUT_AUTH = "vault-auth"

STATUS_OK_ = {"status": "OK"}
DEFAULT_K8S_CTX_ID = "default"
K8S_CTX_PATH = "kctx"


class KctxApi:
    def __init__(self, vault, logger):
        self.vault = vault
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

    def save_aws_context(self, aws_accesskey, aws_secretkey, aws_region, kube_cfg_base64, cluster_name, dns_suffix):
        secret = {"aws_secret_key": aws_secretkey, "aws_access_key": aws_accesskey, "aws_region": aws_region,
                  "kube_config": kube_cfg_base64, "name": cluster_name, "dns_suffix": dns_suffix}
        return self.save_kubernetes_context(secret)

    def get_kubernetes_context(self, ctx_id):
        self.logger.info("Getting kube context")
        if not ctx_id:
            self.logger.warn("Kube ctx \"name\" is empty, using \"default\"")
            ctx_id = DEFAULT_K8S_CTX_ID
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K8S_CTX_PATH, ctx_id)
        try:
            kctx_secret = self.vault.read(kctx_path)
            if not kctx_secret or not kctx_secret["data"]:
                return "No such kctx: {}".format(ctx_id), 1
            return kctx_secret["data"], 0
        except Exception as e:
            self.logger.info("Failed to read secret from path {}, {}".format(kctx_path, e))
            return "Failed to read secret", 1

    def delete_kubernetes_context(self, ctx_id):
        if not ctx_id:
            self.logger.warn("No secret key provided")
            return {"error": "No secret key provided"}
        if ctx_id == "default":
            self.logger.error("Not allowed to remove default kctx")
            return {"error": "Not allowed to remove default kctx"}
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K8S_CTX_PATH, ctx_id)
        try:
            self.vault.delete(kctx_path)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to delete secret from path {}, {}".format(kctx_path, e))
            return {"error": "Failed to delete secret"}

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
                j2_env = Environment(loader=FileSystemLoader("templates"),
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
                j2_env = Environment(loader=FileSystemLoader("templates"),
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

    def setup_traefik(self, kube_env):
        """
        Setup traefik plugin in created cluster

        :param kube_env: env to use for kubernetes communication
        :param tmp_root_path: tmp path to store tmp files
        :return: err code (0 if success), message
        """
        cmd = shlex.split("helm repo add traefik https://containous.github.io/traefik-helm-chart")
        shell_await(cmd, env=kube_env, with_output=True)

        cmd = shlex.split("helm repo update")
        shell_await(cmd, env=kube_env, with_output=True)

        cmd = shlex.split(
            "helm install traefik traefik/traefik --set service.type=NodePort --set ports.web.nodePort=30003")
        return shell_await(cmd, env=kube_env, with_output=True)

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
            j2_env = Environment(loader=FileSystemLoader("templates"),
                                 trim_blocks=True)
            gen_template = j2_env.get_template('{}.j2'.format(template_name)).render(**params)
            f.write(gen_template)
        cmd = shlex.split("kubectl create -f {}".format(f_path))
        return shell_await(cmd, env=kube_env, with_output=True)
