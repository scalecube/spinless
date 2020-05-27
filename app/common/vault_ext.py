import requests
from hvac import exceptions


class VaultOidcExt():
    def __init__(self, base_uri, token):
        self.base_uri = base_uri
        self.token = token
        self.session = requests.Session()

    def oidc_create_key(self, key):
        url = f"v1/identity/oidc/key/{key}"
        payload = {"allowed_client_ids": "*", "verification_ttl": "1h", "rotation_period": "1h"}
        return self.__post(url, payload)

    def oidc_create_role(self, role, key, template):
        url = f"v1/identity/oidc/role/{role}"
        payload = {"key": key, "template": template}
        return self.__post(url, payload)

    def __post(self, url, body):
        return self.__request('post', url, **{'json': body})

    def __request(self, method, url, **kwargs):
        url = self.urljoin(self.base_uri, url)
        headers = {'X-Vault-Token': self.token}
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            **kwargs
        )
        if not response.ok:
            text = errors = None
            if response.headers.get('Content-Type') == 'application/json':
                try:
                    errors = response.json().get('errors')
                except Exception:
                    pass
            if errors is None:
                text = response.text
            self.raise_for_error(
                method,
                url,
                response.status_code,
                text,
                errors=errors
            )

        return response

    @staticmethod
    def urljoin(*args):
        return '/'.join(map(lambda x: str(x).strip('/'), args))

    @staticmethod
    def raise_for_error(method, url, status_code, message=None, errors=None):
        """Helper method to raise exceptions based on the status code of a response received back from Vault.

        :param method: HTTP method of a request to Vault.
        :type method: str
        :param url: URL of the endpoint requested in Vault.
        :type url: str
        :param status_code: Status code received in a response from Vault.
        :type status_code: int
        :param message: Optional message to include in a resulting exception.
        :type message: str
        :param errors: Optional errors to include in a resulting exception.
        :type errors: list | str

        :raises: hvac.exceptions.InvalidRequest | hvac.exceptions.Unauthorized | hvac.exceptions.Forbidden |
            hvac.exceptions.InvalidPath | hvac.exceptions.RateLimitExceeded | hvac.exceptions.InternalServerError |
            hvac.exceptions.VaultNotInitialized | hvac.exceptions.BadGateway | hvac.exceptions.VaultDown |
            hvac.exceptions.UnexpectedError

        """
        if status_code == 400:
            raise exceptions.InvalidRequest(message, errors=errors, method=method, url=url)
        elif status_code == 401:
            raise exceptions.Unauthorized(message, errors=errors, method=method, url=url)
        elif status_code == 403:
            raise exceptions.Forbidden(message, errors=errors, method=method, url=url)
        elif status_code == 404:
            raise exceptions.InvalidPath(message, errors=errors, method=method, url=url)
        elif status_code == 429:
            raise exceptions.RateLimitExceeded(message, errors=errors, method=method, url=url)
        elif status_code == 500:
            raise exceptions.InternalServerError(message, errors=errors, method=method, url=url)
        elif status_code == 501:
            raise exceptions.VaultNotInitialized(message, errors=errors, method=method, url=url)
        elif status_code == 502:
            raise exceptions.BadGateway(message, errors=errors, method=method, url=url)
        elif status_code == 503:
            raise exceptions.VaultDown(message, errors=errors, method=method, url=url)
        else:
            raise exceptions.UnexpectedError(message or errors, method=method, url=url)
