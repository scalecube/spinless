import time
import os
import requests
import tarfile
import yaml

from subprocess import Popen, PIPE
from libs.vault_api import Vault


class Helm:
    def __init__(self, logger, owner, repo, version, helm_version='0.0.1'):
        self.logger = logger
        self.owner = owner
        self.repo = repo
        self.version = version
        self.helm_version = helm_version
        self.timestamp = round(time.time())
        self.path = "/tmp/{}".format(self.timestamp)
        self.helm_dir = "{}/{}-{}".format(self.path, self.owner, self.repo)
        self.namespace = "{}-{}-{}-{}".format(self.path, self.owner, self.repo, self.version)
        self.vault_server = os.getenv("VAULT_ADDR")
        self.service_role = os.getenv("VAULT_ROLE")
        self.vault_secrets_path = os.getenv("VAULT_SECRETS_PATH")

    def get_env_from_vault(self):
        vault = Vault(logger=self.logger,
                      vault_server=self.vault_server,
                      service_role=self.service_role,
                      vault_secrets_path=self.vault_secrets_path
                      )
        return vault.get_self_app_env()

    def sum_all_env(self):
        env_from_vault = self.get_env_from_vault()
        all_env = env_from_vault.update(self.posted_env)
        return all_env

    def untar_helm_gz(self, helm_tag_gz):
        targz = tarfile.open(helm_tag_gz, "r:gz")
        if tarfile.is_tarfile():
            targz.extractall(r"{}".format(self.path))
            return
        else:
            return None

    def prepare_package(self):
        os.mkdir(self.path)
        data = self.get_env_from_vault()
        url = 'https://{}:{}@{}{}-{}-{}.tgz'.format(
            data['nexus_user'], data['nexus_password'], data['nexus_repo'],
            self.owner, self.repo, self.helm_version
        )
        r = requests.get(url)
        helm_tag_gz = '{}/{}-{}.tgz'.format(self.path, self.owner, self.repo)
        with open(helm_tag_gz, "w") as helm_archive:
            helm_archive.write(r.content)
        self.untar_helm_gz(helm_tag_gz)
        return

    def enrich_values_yaml(self):
        with open("{}/values.yaml".format(self.helm_dir)) as default_values_yaml:
            default_values = yaml.load_safe(default_values_yaml)
        vault = Vault(logger=self.logger,
                      vault_server=self.vault_server,
                      service_role=self.service_role,
                      root_path="secretv2",
                      owner=self.owner,
                      repo_slug=self.repo,
                      version=self.version,
                      )
        ### Remove create role
        vault.create_role()
        vault_env = vault.get_env("env")
        env = default_values['env']
        env.update(vault_env)
        default_values['env'] = env
        path_to_values_yaml = "{}/spinless-values.yaml".format(self.helm_dir)
        with open(path_to_values_yaml) as spinless_values_yaml:
            yaml.dump(default_values, spinless_values_yaml, default_flow_style=False)
        return path_to_values_yaml

    def install_package(self):
        self.prepare_package()
        path_to_values_yaml = self.enrich_values_yaml()
        helm_exec = 'helm upgrade --debug --install --namespace {} ' \
                    '--name {} -f {} {} --recreate-pods'.format(
                        self.namespace, self.namespace,
                        path_to_values_yaml, self.helm_dir
        )
        self.logger.info("Helm execution command is: {}".format(helm_exec))
        process = Popen([helm_exec],
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        return
