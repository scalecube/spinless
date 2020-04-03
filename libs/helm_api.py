import time
import os
import requests
import tarfile
import yaml

from subprocess import Popen, PIPE
from libs.vault_api import Vault

class Helm:
    def __init__(self, logger, owner, repo, version, posted_env, helm_version='0.0.1'):
        self.logger = logger
        self.owner = owner
        self.repo = repo
        self.version = version
        self.posted_env = posted_env
        self.helm_version = helm_version
        self.timestamp = round(time.time() * 1000)
        self.path = "/tmp/{}".format(self.timestamp)
        self.helm_dir = "{}/{}-{}".format(self.path, self.owner, self.repo)
        self.namespace = "{}-{}-{}".format(self.owner, self.repo, self.version)
        self.vault = None

    def get_env_from_vault(self):
        vault = Vault(logger=self.logger)
        return vault.get_self_app_env()

    def sum_all_env(self):
        env_from_vault = self.get_env_from_vault()
        all_env = env_from_vault.update(self.posted_env)
        return all_env

    def untar_helm_gz(self, helm_tag_gz):
        self.logger.info("Untar helm_tar_gz is: {}".format(helm_tag_gz))
        targz = tarfile.open(helm_tag_gz, "r:gz")
        targz.extractall(r"{}".format(self.path))
        return

    def prepare_package(self):
        os.mkdir(self.path)
        data = self.get_env_from_vault()
        data = data['data']
        url = 'https://{}:{}@{}{}-{}-{}.tgz'.format(
            data['nexus_user'], data['nexus_password'], data['nexus_repo'],
            self.owner, self.repo, self.helm_version
        )
        r = requests.get(url)
        helm_tag_gz = '{}/{}-{}.tgz'.format(self.path, self.owner, self.repo)
        with open(helm_tag_gz, "wb") as helm_archive:
            helm_archive.write(r.content)
        self.untar_helm_gz(helm_tag_gz)
        return

    def enrich_values_yaml(self):
        with open("{}/values.yaml".format(self.helm_dir)) as default_values_yaml:
            default_values = yaml.load(default_values_yaml, Loader=yaml.FullLoader)
        vault = Vault(logger=self.logger,
                      owner=self.owner,
                      repo=self.repo,
                      version=self.version,
                      )
        ### Remove create role
        vault.create_role()
        vault_env = vault.get_env("env")
        env = default_values['env']
        self.logger.info("Vault values are: {}".format(vault_env))
        self.logger.info("Default values are: {}".format(env))
        env.update(vault_env)
        env.update(self.posted_env)
        default_values['env'] = env
        default_values['service_account'] = "{}-{}".format(self.owner, self.repo)
        self.logger.info("Env before writing: {}".format(default_values))
        path_to_values_yaml = "{}/spinless-values.yaml".format(self.helm_dir)
        with open(path_to_values_yaml, "w") as spinless_values_yaml:
            yaml.dump(default_values, spinless_values_yaml, default_flow_style=False)
        return path_to_values_yaml

    def install_package(self):
        self.prepare_package()
        path_to_values_yaml = self.enrich_values_yaml()
        helm_cmd = os.getenv('HELM_CMD', "/usr/local/bin/helm")
        process = Popen([helm_cmd, "upgrade", "--debug",
                         "--install", "--namespace",
                         "{}".format(self.namespace), "{}".format(self.namespace),
                         "-f", "{}".format(path_to_values_yaml),
                         "{}".format(self.helm_dir), "--recreate-pods"],
                        stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        time.sleep(3)
        self.logger.info("Helm install stdout: {}".format(stdout))
        self.logger.info("Helm install stderr: {}".format(stderr))
        return
