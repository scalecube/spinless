import os

import hvac
from jinja2 import Environment, FileSystemLoader

SECRET_ROOT = "secretv2"

dev_mode = os.getenv("dev_mode", False)

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
        self.vault_secrets_path = os.getenv("VAULT_SECRETS_PATH")
        if dev_mode:
            self.service_role = "developer",
        else:
            self.service_role = os.getenv("VAULT_ROLE")
        self.logger = logger
        self.vault_jwt_token = os.getenv("VAULT_JWT_PATH", '/var/run/secrets/kubernetes.io/serviceaccount/token')
        self.j2_env = Environment(
            loader=FileSystemLoader(f"{os.getenv('APP_WORKING_DIR', os.getcwd())}/common/templates"),
            trim_blocks=True)

    def __create_policy(self):
        policy_name = f"{self.owner}-{self.repo}-policy"
        policies = self.j2_env.get_template('service-policies.j2') \
            .render(secrets_root=SECRET_ROOT, owner=self.owner, repo=self.repo, mount_point=self.mount_point)
        try:
            self.__auth_client()
            self.client.sys.create_or_update_policy(policy_name, policies)
        except Exception as e:
            self.logger.info("Vault create_policy exception is: {}".format(e))
        return policy_name

    def create_role(self):
        self.logger.info("Creating service role")
        policy_name = self.__create_policy()
        try:
            self.__auth_client()
            service_account_name = f'{self.owner}-{self.repo}'
            role_name = f"{service_account_name}-role"
            self.client.create_role(role_name,
                                    mount_point=self.mount_point,
                                    bound_service_account_names=service_account_name,
                                    bound_service_account_namespaces="*",
                                    policies=[policy_name], ttl="1h")
            return role_name, 0
        except Exception as e:
            self.logger.info("Vault create_role exception is: {}".format(e))
            return str(e), 1

    def read(self, path):
        self.__auth_client()
        return self.client.read(path)

    def list(self, path):
        self.__auth_client()
        try:
            result = self.client.list(path)
            if "data" in result:
                return result.get("data").get("keys", [])
            return []
        except Exception as ex:
            self.logger.warning(f"getting secret failed: {ex}")
            return []

    def write(self, path, **data):
        self.__auth_client()
        self.client.write(path, wrap_ttl=None, **data)

    def delete(self, path):
        self.__auth_client()
        self.client.delete(path)

    def prepare_service_path(self, base_ns, target_ns):
        service_path = f"{SECRET_ROOT}/{self.owner}/{self.repo}/{target_ns}"
        if not base_ns:
            self.logger.warning(f"base secrets namespace not provided. will not populate the new secrets")
            return 0, service_path
        base_path = f"{SECRET_ROOT}/{self.owner}/{self.repo}/{base_ns}"
        self.__auth_client()
        try:
            existing = self.client.read(service_path)
            if existing and existing.get('data'):
                return 0, service_path
            else:
                base_secrets = self.client.read(base_path)
                if base_secrets and base_secrets.get('data'):
                    self.client.write(service_path, **base_secrets.get('data'))
        except Exception as e:
            self.logger.warning(f"Failed prepare service path: {e}")
            return 1, str(e)

    def enable_k8_auth(self, cluster_name, reviewer_jwt, kube_ca, kube_serv):
        try:
            self.__auth_client()
            # Configure auth here
            mount_point = 'kubernetes-{}'.format(cluster_name)
            self.client.sys.enable_auth_method(
                method_type='kubernetes',
                path=mount_point,
            )
            self.client.create_kubernetes_configuration(
                kubernetes_host=kube_serv,
                kubernetes_ca_cert=kube_ca,
                token_reviewer_jwt=reviewer_jwt,
                mount_point=mount_point)
            return 0, "success"
        except Exception as e:
            self.logger.warning("Failed to enable k8 auth for {}. Reason: {}".format(cluster_name, e))
            return 1, str(e)

    # Vault's token ttl is too short so this should be called prior to any operation
    def __auth_client(self):
        self.client = hvac.Client()
        try:
            if not self.dev_mode:
                with open(self.vault_jwt_token)as f:
                    jwt = f.read()
                    self.client.auth_kubernetes(self.service_role, jwt)
            else:
                self.client.lookup_token(os.getenv("LOCAL_VAULT_TOKEN"))
        except Exception as ex:
            print(f"Error authenticating vault: {str(ex)}")
