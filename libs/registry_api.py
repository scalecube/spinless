class RegistryApi:
    def __init__(self, vault, logger):
        self.vault = vault
        self.v_client = vault.client
        self.logger = logger

    def save_reg(self, reg_data):
        type = reg_data["type"]
        if type not in ("docker", "helm"):
            self.logger.error("Field \'type\' should be one of \'helm\' or \'docker\' but was {}".format(type))
            return {"error": "Missing type (docker/helm)"}
        if not all(k in reg_data for k in ("name", "username", "password", "path")):
            self.logger.error("Mandatory fields not provided (\"name\",\"username\", \"password\", \"path\")")
            return {"error": "Missing mandatory fields"}
        reg_path = "{}/registry/{}/{}".format(self.vault.root_path, type, reg_data["name"])
        secret_payload = dict((k, reg_data) for k in ("username", "password", "path"))
        try:
            self.logger.info("Saving registry data into path: {}".format(reg_path))
            return self.v_client.write(reg_path, secret_payload)
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
        reg_path = "{}/registry/{}/{}".format(self.vault.root_path, reg_type, reg_data["name"])
        try:
            return self.v_client.read(reg_path)
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
        reg_path = "{}/registry/{}/{}".format(self.vault.root_path, reg_type, reg_data["name"])
        try:
            return self.v_client.delete(reg_path)
        except Exception as e:
            self.logger.info("Failed to delete secret from path {}, {}".format(reg_path, e))
            return {"error": "Failed to delete secret"}
