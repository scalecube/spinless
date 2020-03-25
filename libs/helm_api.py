from subprocess import Popen, PIPE


class Helm:
    def __init__(self):
        pass

    def get_env_from_vault(self):
        return {}

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
