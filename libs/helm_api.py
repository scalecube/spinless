import time
import os
import requests
from subprocess import Popen, PIPE

from libs.vault_api import Vault


class Helm:
    def __init__(self, logger, owner, repo, helm_version='0.0.1'):
        self.logger = logger
        self.owner = owner
        self.repo = repo
        self.helm_version = helm_version
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
        path = "/tmp/{}".format(self.timestamp)
        os.mkdir(path)
        data = self.get_env_from_vault
        url = 'https://{}:{}@{}{}-{}-{}.tgz'.format(
            data['nexus_user'], data['nexus_password'], data['nexus_repo'],
            data['owner'], data['repo'], self.helm_version
        )
        r = requests.get(url)
        with open('{}/{}-{}.tgz'.format(data['owner'], data['repo'])) as helm_archive:
            helm_archive.write(r.content)



    def enrich_values_yaml(self):
        pass

    def install_package(self):
        process = Popen(['helm --install --upgrade --debug'.format()],
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        pass
