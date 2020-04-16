import boto3
import yaml

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

    def save_aws_context(self, aws_accesskey, aws_secretkey, aws_region, kube_cfg_dict, conf_label="default"):
        secret = {"aws_secret_key": aws_secretkey, "aws_access_key": aws_accesskey, "aws_region": aws_region,
                  "kube_config": kube_cfg_dict, "name": conf_label}
        return self.save_kubernetes_context(secret)

    def get_kubernetes_context(self, ctx_id):
        self.logger.info("Getting kube context")
        self.logger.info("K8S_CTX_PATH is {}".format(K8S_CTX_PATH))
        if not ctx_id:
            self.logger.warn("Kube ctx \"name\" is empty, using \"default\"")
            ctx_id = DEFAULT_K8S_CTX_ID
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K8S_CTX_PATH, ctx_id)
        self.logger.info("kctx_path is: ".format(kctx_path))
        try:
            kctx_secret = self.vault.read(kctx_path)
            self.logger.info("kctx_path: ".format(kctx_path))
            if not kctx_secret or not kctx_secret["data"]:
                return {"error": "No such kctx: {}".format(ctx_id)}
            return kctx_secret["data"]
        except Exception as e:
            self.logger.info("Failed to read secret from path {}, {}".format(kctx_path, e))
            return {"error": "Failed to read secret"}

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
                                 aws_access_key, aws_secret_key):
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

            # build the cluster config hash
            cluster_config = {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [
                    {
                        "cluster": {
                            "server": str(cluster_ep),
                            "certificate-authority-data": str(cluster_cert)
                        },
                        "name": "kubernetes"
                    }
                ],
                "contexts": [
                    {
                        "context": {
                            "cluster": "kubernetes",
                            "user": "aws"
                        },
                        "name": "aws"
                    }
                ],
                "current-context": "aws",
                "preferences": {},
                "users": [
                    {
                        "name": "aws",
                        "user": {
                            "exec": {
                                "apiVersion": "client.authentication.k8s.io/v1alpha1",
                                "command": "aws-iam-authenticator",
                                "args": [
                                    "token", "-i", cluster_name
                                ]
                            }
                        }
                    }
                ]
            }
        except Exception as ex:
            return str(ex), 1
        return cluster_config, 0
