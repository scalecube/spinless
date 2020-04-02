import os

import hvac

dev_mode = os.getenv("dev_mode", False)

dev_settings = {
    "vault_addr": "localhost",
    "vault_role": "developer",
    "vault_secr_path": "secretv2",
    "vault_token": "s.e1L8vQHYaxrCIpRcCgWwMDgC"
}


class Vault:
    def __init__(self, logger,
                 root_path="secretv2",
                 owner=None,
                 repo=None,
                 version=None):
        self.root_path = root_path
        self.owner = owner
        self.repo = repo
        self.version = version
        self.app_path = "{}-{}-{}".format(owner, repo, version)
        self.dev_mode = dev_mode
        if dev_mode:
            self.vault_server = dev_settings["vault_addr"],
            self.service_role = dev_settings["vault_role"],
            self.vault_secrets_path = dev_settings["vault_secr_path"]
        else:
            self.vault_server = os.getenv("VAULT_ADDR")
            self.service_role = os.getenv("VAULT_ROLE")
            self.vault_secrets_path = os.getenv("VAULT_SECRETS_PATH")
        self.logger = logger

        # init client
        self.client = hvac.Client(url=self.vault_server)
        try:
            if not self.dev_mode:
                f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
                jwt = f.read()
                self.client.auth_kubernetes(self.service_role, jwt)
            else:
                self.client.lookup_token(dev_settings["vault_token"])
        except Exception as ex:
            print("Error authenticating vault: {}".format(ex))



    def get_self_app_env(self):
        try:
            self.logger.info("Vault secrets path is: {}".format(self.vault_secrets_path))
            env = self.client.read(self.vault_secrets_path)
            if not env or not env['data']:
                self.logger.error("Data not found for secret path {}".format(self.vault_secrets_path))
                return {}
            return env
        except Exception as e:
            self.logger.info("Vault get_self_app_env exception is: {}".format(e))
            return {}

    def get_env(self, env_or_app):
        path = "{}/{}/{}/{}/{}".format(
            self.root_path, self.owner, self.repo, self.version, env_or_app)
        self.logger.info("Get_env in vault path is: {}".format(path))
        try:
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
            self.client.set_policy(policy_name, policy_1_path + policy_2_path)
        except Exception as e:
            self.logger.info("Vault create_policy exception is: {}".format(e))
        return policy_name

    def create_role(self):
        self.logger.info("Creating service role")
        policy_name = self.create_policy()
        try:
            self.client.create_role("{}-role".format(self.app_path),
                                    mount_point="kubernetes",
                                    bound_service_account_names="{}".format(self.app_path),
                                    bound_service_account_namespaces="*",
                                    policies=[policy_name], ttl="1h")
        except Exception as e:
            self.logger.info("Vault create_role exception is: {}".format(e))
        return
