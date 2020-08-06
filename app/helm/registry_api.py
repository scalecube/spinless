from common.vault_api import Vault

APP_REG_PATH = "registries"


class RegistryApi:
    def __init__(self, logger):
        self.vault = Vault(logger)
        self.logger = logger

    def get_registry(self, registry_type, registry_name):
        """
        Get registry by type and name
        :param registry_type type of registry, currently supported are "docker"/"helm"
        :param registry_name name of registry to get
        :return: (registry data, 0) in case of success, (error string , error code) otherwise
        """

        if registry_type not in ("docker", "helm"):
            return f"Supported registry types are docker/helm, not {registry_type}", 1
        reg_path = f"{self.vault.base_path}/{APP_REG_PATH}/{registry_type}/{registry_name}"
        try:
            registry_secret = self.vault.read(reg_path)
            if not registry_secret or not registry_secret["data"]:
                return f'No such {registry_type} registry: {registry_name}', 1
            return registry_secret["data"], 0
        except Exception as e:
            return f'Failed to read secret from path {reg_path}, {str(e)}', 1
