import os

import hvac
from jinja2 import Environment, FileSystemLoader

MOUNT_POINT = "kubernetes"
SECRET_ROOT = "secretv2"

dev_mode = os.getenv("DEV_MODE", False)

APP_ENV_PATH = "app_env"


class Vault:
    def __init__(self, logger,
                 owner=None,
                 repo=None,
                 cluster_name=''):
        self.owner = owner
        self.repo = repo
        self.mount_point = f'kubernetes-{cluster_name}'
        self.dev_mode = dev_mode
        self.base_path = os.getenv("VAULT_SECRETS_PATH")
        if dev_mode:
            self.service_role = "developer",
        else:
            self.service_role = os.getenv("VAULT_ROLE")
        self.logger = logger
        self.vault_jwt_token = os.getenv("VAULT_JWT_PATH", '/var/run/secrets/kubernetes.io/serviceaccount/token')
        self.j2_env = Environment(
            loader=FileSystemLoader(f"{os.getenv('APP_WORKING_DIR', os.getcwd())}/common/templates"),
            trim_blocks=True)

    def delete(self, path):
        try:
            self.__auth_client()
            self.client.delete(path)
            return path, 0
        except Exception as ex:
            return str(ex), 1

    def delete_service_path(self, namespace):
        return self.delete(f'{SECRET_ROOT}/{self.owner}/{self.repo}/{namespace}')

    def prepare_service_path(self, base_ns, target_ns):
        service_path = f"{SECRET_ROOT}/{self.owner}/{self.repo}/{target_ns}"
        if not base_ns:
            self.logger.warning(f"base secrets namespace not provided. will not populate the new secrets")
            return service_path, 0
        base_path = f"{SECRET_ROOT}/{self.owner}/{self.repo}/{base_ns}"
        self.__auth_client()
        try:
            existing = self.client.read(service_path)
            if existing and existing.get('data'):
                return service_path, 0
            else:
                base_secrets = self.client.read(base_path)
                if base_secrets and base_secrets.get('data'):
                    self.client.write(service_path, **base_secrets.get('data'))
        except Exception as e:
            self.logger.warning(f"Failed prepare service path: {e}")
            return str(e), 1

    def disable_vault_mount_point(self, cluster_name):
        try:
            self.__auth_client()
            # Configure auth here
            mount_point = 'kubernetes-{}'.format(cluster_name)
            self.client.sys.disable_auth_method(
                path=mount_point,
            )
            return 0, "success"
        except Exception as e:
            self.logger.warning(f"Failed to disable k8 auth for {cluster_name}. Reason: {e}")
            return 1, str(e)
