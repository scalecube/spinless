import os

import hvac

dev_mode = os.getenv("dev_mode", False)

dev_settings = {
    "vault_role": "developer",
}

APP_ENV_PATH = "app_env"


class Vault:
    def __init__(self, logger,
                 root_path="secretv2",
                 owner=None,
                 repo=None,
                 branch_name=None):
        self.root_path = root_path
        self.owner = owner
        self.repo = repo
        self.branch_name = branch_name
        self.app_path = "{}-{}-{}".format(owner, repo, branch_name)
        self.dev_mode = dev_mode
        self.vault_secrets_path = os.getenv("VAULT_SECRETS_PATH")
        if dev_mode:
            self.service_role = dev_settings["vault_role"],
        else:
            self.service_role = os.getenv("VAULT_ROLE")
        self.logger = logger
        self.vault_jwt_token = os.getenv("VAULT_JWT_PATH", '/var/run/secrets/kubernetes.io/serviceaccount/token')


    def get_self_app_env(self):
        try:
            self.__auth_client()
            app_secret_path = self.vault_secrets_path + "/" + APP_ENV_PATH
            self.logger.info("Vault secrets path is: {}".format(app_secret_path))
            env = self.client.read(app_secret_path)
            if not env or not env['data']:
                self.logger.error("Data not found for secret path {}".format(app_secret_path))
                return {}
            return env
        except Exception as e:
            self.logger.info("Vault get_self_app_env exception is: {}".format(e))
            return {}

    def get_env(self):
        path = "{}/{}/{}/{}".format(
            self.root_path, self.owner, self.repo, self.branch_name)
        self.logger.info("Get_env in vault path is: {}".format(path))
        try:
            self.__auth_client()
            env = self.client.read(path)
            self.logger.info("ENV from vault is {}: ".format(env))
            return env['data']
        except Exception as e:
            self.logger.info("Vault get_env exception is: {}".format(e))
            return {}

    def create_policy(self):
        policy_name = "{}-{}-policy".format(self.owner, self.repo)
        policy_path = "{}/{}/{}/*".format(self.root_path, self.owner, self.repo)
        self.logger.info("Policy name is: {}".format(policy_name))
        self.logger.info("Policy path is: {}".format(policy_path))
        policy_1_path = 'path "{}" '.format(policy_path)
        policy_2_path = '{ capabilities = ["create", "read", "update", "delete", "list"]}'
        try:
            # self.client.set_policy(policy_name, policy_1_path + policy_2_path) - DEPRECATED
            self.__auth_client()
            self.client.sys.create_or_update_policy(policy_name, policy_1_path + policy_2_path)
        except Exception as e:
            self.logger.info("Vault create_policy exception is: {}".format(e))
        return policy_name

    def create_role(self):
        self.logger.info("Creating service role")
        policy_name = self.create_policy()
        try:
            self.__auth_client()
            self.client.create_role("{}-role".format(self.app_path),
                                    mount_point="kubernetes",
                                    bound_service_account_names="{}".format(self.app_path),
                                    bound_service_account_namespaces="*",
                                    policies=[policy_name], ttl="1h")
        except Exception as e:
            self.logger.info("Vault create_role exception is: {}".format(e))
        return

    def read(self, path):
        self.__auth_client()
        return self.client.read(path)

    def write(self, path, **data):
        self.__auth_client()
        self.client.write(path, wrap_ttl=None, **data)

    def delete(self, path):
        self.__auth_client()
        self.client.delete(path)

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
            print("Error authenticating vault: {}".format(ex))
