import os

import hvac

SECRET_ROOT_DEFAULT = "secretv2"

dev_mode = os.getenv("dev_mode", False)

APP_ENV_PATH = "app_env"


class Vault:
    def __init__(self, logger,
                 root_path=SECRET_ROOT_DEFAULT,
                 owner=None,
                 repo=None,
                 branch=None):
        self.root_path = root_path
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.app_path = "{}-{}-{}".format(owner, repo, branch)
        self.dev_mode = dev_mode
        self.vault_secrets_path = os.getenv("VAULT_SECRETS_PATH")
        if dev_mode:
            self.service_role = "developer",
        else:
            self.service_role = os.getenv("VAULT_ROLE")
        self.logger = logger
        self.vault_jwt_token = os.getenv("VAULT_JWT_PATH", '/var/run/secrets/kubernetes.io/serviceaccount/token')

    def __create_policy(self):
        policy_name = "{}-{}-policy".format(self.owner, self.repo)
        policy_path = "{}/{}/{}/*".format(self.root_path, self.owner, self.repo)
        self.logger.info("Policy name is: {}".format(policy_name))
        self.logger.info("Policy path is: {}".format(policy_path))
        policy_1_path = 'path "{}" '.format(policy_path)
        policy_2_path = '{ capabilities = ["read", "list"]}'
        try:
            # self.client.set_policy(policy_name, policy_1_path + policy_2_path) - DEPRECATED
            self.__auth_client()
            self.client.sys.create_or_update_policy(policy_name, policy_1_path + policy_2_path)
        except Exception as e:
            self.logger.info("Vault create_policy exception is: {}".format(e))
        return policy_name

    def create_role(self, cluster_name):
        self.logger.info("Creating service role")
        policy_name = self.__create_policy()
        try:
            self.__auth_client()
            role_name = "{}-role".format(self.app_path)
            self.client.create_role(role_name,
                                    mount_point="kubernetes-{}".format(cluster_name),
                                    bound_service_account_names="{}".format(self.app_path),
                                    bound_service_account_namespaces="*",
                                    policies=[policy_name], ttl="1h")
            return role_name, 0
        except Exception as e:
            self.logger.info("Vault create_role exception is: {}".format(e))
            return str(e), 1

    def read(self, path):
        self.__auth_client()
        return self.client.read(path)

    def write(self, path, **data):
        self.__auth_client()
        self.client.write(path, wrap_ttl=None, **data)

    def delete(self, path):
        self.__auth_client()
        self.client.delete(path)

    def enable_k8_auth(self, cluster_name, reviewer_jwt, kube_ca, kube_serv):
        try:
            self.__auth_client()
            ### Configure auth here
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
            print("Error authenticating vault: {}".format(ex))
