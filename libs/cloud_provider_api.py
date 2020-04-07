STATUS_OK_ = {"status": "OK"}
DEFAULT_SECRET_KEY = "default"
SECRET_RELATIVE_PATH = "cloud/providers"


class CloudApi:
    __MANDATORY_FIELDS = ("name", "provider")

    def __init__(self, vault, logger):
        self.vault = vault
        self.v_client = vault.client
        self.logger = logger

    def save_cloud_provider(self, data):
        if not data:
            self.logger.error("No data provided")
            return {"error": "No data provided"}
        if not all(k in data for k in self.__MANDATORY_FIELDS):
            self.logger.error("Mandatory fields not provided: {}".format(self.__MANDATORY_FIELDS))
            return {"error": "Mandatory fields not provided: {}".format(self.__MANDATORY_FIELDS)}
        secret_path = "{}/{}/{}/{}".format(self.vault.vault_secrets_path, SECRET_RELATIVE_PATH, data.pop("provider"),
                                           data.pop("name"))
        try:
            self.logger.info("Saving data into path: {}".format(secret_path))
            self.v_client.write(secret_path, wrap_ttl=None, **data)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to write secret to path {}, {}".format(secret_path, e))
            return {"error": "Failed to write secret"}

    def get_cloud_provider(self, data):
        if not data or not all(k in data for k in self.__MANDATORY_FIELDS):
            self.logger.warn("not enough input to get secret, using \"default\"")
            data = DEFAULT_SECRET_KEY
        secret_path = "{}/{}/{}".format(self.vault.vault_secrets_path, SECRET_RELATIVE_PATH, data)
        try:
            secret = self.v_client.read(secret_path)
            if not secret or not secret["data"]:
                return {"error": "No such entity: {}".format(data)}
            return secret["data"]
        except Exception as e:
            self.logger.info("Failed to read secret from path {}, {}".format(secret_path, e))
            return {"error": "Failed to read secret"}

    def delete_cloud_provider(self, secret_id):
        if not secret_id:
            self.logger.error("No secret key provided")
            return {"error": "No secret key provided"}
        if secret_id == DEFAULT_SECRET_KEY:
            self.logger.error("Not allowed to remove default value")
            return {"error": "Not allowed to remove default value"}
        secret_path = "{}/{}/{}".format(self.vault.vault_secrets_path, SECRET_RELATIVE_PATH, secret_id)
        try:
            self.v_client.delete(secret_path)
            return STATUS_OK_
        except Exception as e:
            self.logger.info("Failed to delete secret from path {}, {}".format(secret_path, e))
            return {"error": "Failed to delete secret"}
