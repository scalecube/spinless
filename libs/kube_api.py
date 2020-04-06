STATUS_OK_ = {"status": "OK"}
DEFAULT_KCTX_ID = "default"
K_CTX_PATH = "kctx"


class KctxApi:
    def __init__(self, vault, logger):
        self.vault = vault
        self.v_client = vault.client
        self.logger = logger

    def save_k_ctx(self, ctx_data):
        if not ctx_data:
            self.logger.error("No kube ctx data provided")
            return {"error": "No kube ctx data provided"}
        if not all(k in ctx_data for k in ("name", "kctx_name")):
            self.logger.error("Mandatory fields not provided (\"name\", \"kctx_name\")")
            return {"error": "Mandatory fields not provided (\"name\", \"kctx_name\")"}
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K_CTX_PATH, ctx_data["name"])
        secret_payload = {"kctx_name": ctx_data["kctx_name"]}
        try:
            self.logger.info("Saving kube ctx data into path: {}".format(kctx_path))
            self.v_client.write(kctx_path, wrap_ttl=None, **secret_payload)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to write secret to path {}, {}".format(kctx_path, e))
            return {"error": "Failed to write secret"}

    def get_kctx(self, ctx_id):
        if not ctx_id:
            self.logger.warn("Kube ctx \"name\" is empty, using \"default\"")
            ctx_id = DEFAULT_KCTX_ID
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K_CTX_PATH, ctx_id)
        try:
            kctx_secret = self.v_client.read(kctx_path)
            if not kctx_secret or not kctx_secret["data"]:
                return {"error": "No such kctx: {}".format(ctx_id)}
            return kctx_secret["data"]
        except Exception as e:
            self.logger.info("Failed to read secret from path {}, {}".format(kctx_path, e))
            return {"error": "Failed to read secret"}

    def delete_kctx(self, ctx_id):
        if not ctx_id:
            self.logger.warn("Kctx \"name\" is empty, using default")
            return {"error": "Kctx \"name\" is mandatory"}
        if ctx_id == "default":
            self.logger.error("Not allowed to remove default kctx")
            return {"error": "Not allowed to remove default kctx"}
        kctx_path = "{}/{}/{}".format(self.vault.vault_secrets_path, K_CTX_PATH, ctx_id)
        try:
            self.v_client.delete(kctx_path)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to delete secret from path {}, {}".format(kctx_path, e))
            return {"error": "Failed to delete secret"}
