import hvac


class Vault:
    def __init__(self, logger,
                 vault_server,
                 service_role,
                 root_path=None,
                 owner=None,
                 repo_slug=None,
                 version=None,
                 vault_secrets_path=None):
        self.root_path = root_path
        self.owner = owner
        self.repo_slug = repo_slug
        self.version = version
        self.app_path = "{}-{}-{}".format(owner, repo_slug, version)
        self.vault_server = vault_server
        self.service_role = service_role
        self.logger = logger
        self.vault_secrets_path = vault_secrets_path
        self.client = hvac.Client(url=vault_server)

    def auth_client(self):
        f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
        jwt = f.read()
        self.client.auth_kubernetes(self.service_role, jwt)
        return self.client

    def get_self_app_env(self):
        client = self.auth_client()
        try:
            env = client.read(self.vault_secrets_path)['data']
            return env
        except Exception as e:
            self.logger.info("Vault get_self_app_env exception is: {}".format(e))
            return {}

    def get_env(self, env_or_app):
        client = self.auth_client()
        try:
            env = client.read("{}/{}/{}".format(
                self.root_path, self.app_path, env_or_app))['data']
            return env
        except Exception as e:
            self.logger.info("Vault get_env exception is: {}".format(e))
            return {}

    def create_policy(self):
        client = self.auth_client()
        policy_name = "{}-policy".format(self.app_path)
        try:
            client.set_policy(policy_name,
                              'path "{}/{}/*" { capabilities = ["create", "read", "update", "delete", "list"]}'.format(
                                  self.root_path, self.app_path))
        except Exception as e:
            self.logger.info("Vault create_policy exception is: {}".format(e))
        return policy_name

    def create_role(self):
        client = self.auth_client()
        policy_name = self.create_policy()
        try:
            client.create_role("{}-role".format(self.app_path),
                               mount_point="kubernetes",
                               bound_service_account_names="{}".format(self.app_path),
                               bound_service_account_namespaces="*",
                               policies=[policy_name], ttl="1h")
        except Exception as e:
            self.logger.info("Vault create_role exception is: {}".format(e))
        return

