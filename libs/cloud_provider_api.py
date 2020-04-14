STATUS_OK_ = {"status": "OK"}
DEFAULT_SECRET_KEY = "default"
DEFAULT_PROVIDER = "eks"
SECRET_RELATIVE_PATH = "cloud/providers"


class CloudApi:
    __MANDATORY_FIELDS = ("name", "type")

    def __init__(self, vault, logger):
        self.vault = vault
        self.logger = logger

    def save_cloud_provider(self, data):
        if not data:
            self.logger.error("No data provided")
            return {"error": "No data provided"}
        if not all(k in data for k in self.__MANDATORY_FIELDS):
            self.logger.error("Mandatory fields not provided: {}".format(self.__MANDATORY_FIELDS))
            return {"error": "Mandatory fields not provided: {}".format(self.__MANDATORY_FIELDS)}
        secret_path = "{}/{}/{}/{}".format(self.vault.vault_secrets_path, SECRET_RELATIVE_PATH, data.pop("type"),
                                           data.pop("name"))
        try:
            self.logger.info("Saving data into path: {}".format(secret_path))
            self.vault.write(secret_path, wrap_ttl=None, **data)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to write secret to path {}, {}".format(secret_path, e))
            return {"error": "Failed to write secret"}

    def get_cloud_provider(self, data):
        type = data.get("type", DEFAULT_PROVIDER)
        name = data.get("name", DEFAULT_SECRET_KEY)
        secret_path = "{}/{}/{}/{}".format(self.vault.vault_secrets_path, SECRET_RELATIVE_PATH, type, name)
        try:
            secret = self.vault.read(secret_path)
            if not secret or not secret["data"]:
                return {"error": "No such entity: {}/{}".format(type, name)}
            return secret["data"]
        except Exception as e:
            self.logger.info("Failed to read secret from path {}, {}".format(secret_path, e))
            return {"error": "Failed to read secret"}

    def delete_cloud_provider(self, p_type, name):
        if not p_type or not name:
            self.logger.error("Mandatory fields not provided")
            return {"error": "Mandatory fields not provided"}
        if name == DEFAULT_SECRET_KEY:
            self.logger.error("Not allowed to remove default value")
            return {"error": "Not allowed to remove default value"}
        secret_path = "{}/{}/{}/{}".format(self.vault.vault_secrets_path, SECRET_RELATIVE_PATH, p_type, name)
        try:
            self.vault.delete(secret_path)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to delete secret from path {}, {}".format(secret_path, e))
            return {"error": "Failed to delete secret"}
