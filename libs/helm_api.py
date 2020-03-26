import time
import os
from subprocess import Popen, PIPE

from libs.vault_api import Vault


class Helm:
    def __init__(self, logger):
        self.logger = logger
        self.timestamp = round(time.time())
        pass

    def get_env_from_vault(self):
        vault = Vault(logger=self.logger,
                      vault_server=os.getenv("VAULT_ADDR"),
                      service_role=os.getenv("VAULT_ROLE"),
                      vault_secrets_path=os.getenv("VAULT_SECRETS_PATH")
                      )
        return vault.get_self_app_env()

    def sum_all_env(self):
        env_from_vault = self.get_env_from_vault()
        all_env = env_from_vault.update(self.posted_env)
        return all_env

    def get_package(self):
        process = Popen(['wget', 'https://{}:{}@{}{}-{}-{}.tgz'.format(
            nexus_user, nexus_password, nexus_repo, owner, repo, helm_version
        )], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

    def enrich_values_yaml(self):
        pass

    def install_package(self):
        pass
