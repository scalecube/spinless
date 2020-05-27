import os

import hvac

from common.vault_ext import VaultOidcExt

SECRET_ROOT = "secretv2"

dev_mode = os.getenv("dev_mode", False)

APP_ENV_PATH = "app_env"
M2M_AUTH_ENABLED = os.getenv("M2M_AUTH_ENABLED", False)


class Vault:
    def __init__(self, logger,
                 owner=None,
                 repo=None):
        self.owner = owner
        self.repo = repo
        self.dev_mode = dev_mode
        self.vault_secrets_path = os.getenv("VAULT_SECRETS_PATH")
        if dev_mode:
            self.service_role = "developer",
        else:
            self.service_role = os.getenv("VAULT_ROLE")
        self.logger = logger
        self.vault_jwt_token = os.getenv("VAULT_JWT_PATH", '/var/run/secrets/kubernetes.io/serviceaccount/token')
        self.client = hvac.Client()
        self.oidc_client = VaultOidcExt()

    def __create_policy(self):
        policy_name = f'{self.owner}-{self.repo}-policy'
        service_path = f'{SECRET_ROOT}/{self.owner}/{self.repo}/*'
        service_policy = f'path "{service_path}" {{ capabilities = ["create", "read", "update", "delete", "list"]}}'
        try:
            self.__auth_client()
            self.client.sys.create_or_update_policy(policy_name, service_policy)
        except Exception as e:
            self.logger.info("Vault create_policy exception is: {}".format(e))
        return policy_name

    def create_role(self, cluster_name):
        self.logger.info("Creating service role")
        policies = [self.__create_policy()]
        consumer_policy_name = f"{self.owner}-{self.repo}-service-consumer-policy"
        if M2M_AUTH_ENABLED:
            policies.append(consumer_policy_name)
        try:
            self.__auth_client()
            service_account_name = f'{self.owner}-{self.repo}'
            role_name = f"{service_account_name}-role"
            self.client.create_role(role_name,
                                    mount_point=f"kubernetes-{cluster_name}",
                                    bound_service_account_names=service_account_name,
                                    bound_service_account_namespaces="*",
                                    policies=policies, ttl="1h")
            return role_name, 0
        except Exception as e:
            self.logger.info("Vault create_role exception is: {}".format(e))
            return str(e), 1

    def setup_oidc(self, roles):
        if not M2M_AUTH_ENABLED or len(roles) == 0:
            return 0, 'ok'
        oidc_key = f'{self.owner}-{self.repo}'
        try:
            self.__auth_client()
            self.oidc_client.oidc_create_key(oidc_key)
            self.logger.debug(f'oidc key created: {oidc_key}')

            for role in roles:
                # creatre oidc role
                template = f'{{"permissions":"{role}"}}'
                self.oidc_client.oidc_create_role(role, oidc_key, template)
                self.logger.debug(f'oidc role created: "{role}". template: "{template}"')

                # create policy
                oidc_policy_name = f"{role}-id-token-policy"
                oidc_policy = f'path "identity/oidc/token/{role}" {{capabilities=["read"]}}'
                self.client.sys.create_or_update_policy(oidc_policy_name, oidc_policy)

        except Exception as e:
            return 1, str(e)

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
            self.oidc_client = VaultOidcExt(self.client.url, self.client.token)
        except Exception as ex:
            print("Error authenticating vault: {}".format(ex))
