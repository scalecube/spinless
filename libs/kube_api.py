import yaml
import boto3


STATUS_OK_ = {"status": "OK"}
DEFAULT_K8S_CTX_ID = "default"
K8S_CTX_PATH = "kctx"


class KctxApi:
    def __init__(self, vault, logger):
        self.vault = vault
        self.v_client = vault.client
        self.logger = logger

    def save_kubernetes_context(self, ctx_data):
        if not ctx_data:
            self.logger.error("No kube ctx data provided")
            return {"error": "No kube ctx data provided"}
        if not all(k in ctx_data for k in ("name", "kctx_name")):
            self.logger.error("Mandatory fields not provided (\"name\", \"kctx_name\")")
            return {"error": "Mandatory fields not provided (\"name\", \"kctx_name\")"}
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K8S_CTX_PATH, ctx_data["name"])
        secret_payload = {"kctx_name": ctx_data["kctx_name"]}
        try:
            self.logger.info("Saving kube ctx data into path: {}".format(kctx_path))
            self.v_client.write(kctx_path, wrap_ttl=None, **secret_payload)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to write secret to path {}, {}".format(kctx_path, e))
            return {"error": "Failed to write secret"}

    def get_kubernetes_context(self, ctx_id):
        if not ctx_id:
            self.logger.warn("Kube ctx \"name\" is empty, using \"default\"")
            ctx_id = DEFAULT_K8S_CTX_ID
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K8S_CTX_PATH, ctx_id)
        try:
            kctx_secret = self.v_client.read(kctx_path)
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
            self.v_client.delete(kctx_path)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to delete secret from path {}, {}".format(kctx_path, e))
            return {"error": "Failed to delete secret"}

    # TODO: get region, aws_access_key_id, aws_secret_access_key from vault, aws configure
    # TODO: remove staticmethod ???
    @staticmethod
    def generate_cluster_config(cluster_name, config_file):
        # Set up the client
        s = boto3.Session()
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

        # Write in YAML
        with open(config_file, "w") as kube_config_file:
            yaml.dump(cluster_config, kube_config_file, default_flow_style=False)

