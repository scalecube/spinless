STATUS_OK_ = {"status": "OK"}
APP_REG_PATH = "registries"


class RegistryApi:
    def __init__(self, vault, logger):
        self.vault = vault
        self.v_client = vault.client
        self.logger = logger

    def save_reg(self, reg_data):
        reg_type = reg_data["type"]
        if reg_type not in ("docker", "helm"):
            self.logger.error("Field \'type\' should be one of \'helm\' or \'docker\' but was {}".format(reg_type))
            return {"error": "Missing type (docker/helm)"}
        if not all(k in reg_data for k in ("name", "username", "password", "repo_path")):
            self.logger.error("Mandatory fields not provided (\"name\",\"username\", \"password\", \"repo_path\")")
            return {"error": "Missing mandatory fields"}
        reg_path = "{}/{}/{}/{}".format(self.vault.vault_secrets_path, APP_REG_PATH, reg_type, reg_data["name"])
        secret_payload = dict((k, reg_data[k]) for k in ("username", "password", "repo_path"))
        try:
            self.logger.info("Saving registry data into path: {}".format(reg_path))
            self.v_client.write(reg_path, wrap_ttl=None, **secret_payload)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to write secret to path {}, {}".format(reg_path, e))
            return {"error": "Failed to write secret"}

    def get_reg(self, reg_data):
        reg_type = reg_data["type"]
        if reg_type not in ("docker", "helm"):
            self.logger.error("Field \'type\' should be one of \'helm\' or \'docker\' but was {}".format(reg_type))
            return {"error": "Missing type (docker/helm)"}
        if not reg_data["name"]:
            self.logger.error("Repo \"name\" is mandatory")
            return {"error": "Repo \"name\" is mandatory"}
        reg_path = "{}/{}/{}/{}".format(self.vault.vault_secrets_path, APP_REG_PATH, reg_type, reg_data["name"])
        try:
            reg_secret = self.v_client.read(reg_path)
            if not reg_secret or not reg_secret["data"]:
                return {"error": "No such registry: {}".format(reg_data)}
            return reg_secret["data"]
        except Exception as e:
            self.logger.info("Failed to read secret from path {}, {}".format(reg_path, e))
            return {"error": "Failed to read secret"}

    def delete_reg(self, reg_data):
        reg_type = reg_data["type"]
        if reg_type not in ("docker", "helm"):
            self.logger.error("Field \'type\' should be one of \'helm\' or \'docker\' but was {}".format(reg_type))
            return {"error": "Missing type (docker/helm)"}
        if not reg_data["name"]:
            self.logger.error("Repo \"name\" is mandatory")
            return {"error": "Repo \"name\" is mandatory"}
        if reg_data["name"] == "default":
            self.logger.error("Not allowed to remove default registry")
            return {"error": "Not allowed to remove default registry"}
        reg_path = "{}/{}/{}/{}".format(self.vault.vault_secrets_path, APP_REG_PATH, reg_type, reg_data["name"])
        try:
            self.v_client.delete(reg_path)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to delete secret from path {}, {}".format(reg_path, e))
            return {"error": "Failed to delete secret"}
