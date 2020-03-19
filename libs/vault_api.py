import hvac


class Vault:
    def __init__(self, root_path,
                 vault_server,
                 service_role,
                 repo_slug,
                 version):
        self.root_path = root_path
        self.vault_server = vault_server
        self.service_role = service_role
        self.repo_slug = repo_slug
        self.version = version
        self.client = hvac.Client(url=vault_server)

    def auth_client(self):
        f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
        jwt = f.read()
        self.client.auth_kubernetes(self.service_role, jwt)
        return

    def get_data(self, env):
        f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
        jwt = f.read()
        client = hvac.Client(url=self.vault_server)
        client.auth_kubernetes(self.service_role, jwt)
        try:
            app_data = client.read("{}/{}/{}/app_data".format(
                self.root_path, self.repo_slug, env))['data']
            return app_data
        except Exception as e:
            pass
            return {}
