import multiprocessing
import os
from logging.config import dictConfig

from dotenv import load_dotenv, find_dotenv
from flasgger import Swagger
from flask import request, Response, abort, jsonify
from flask_api import FlaskAPI

from common.authentication import AuthError, get_token, requires_auth, requires_account
from common import authentication
from common.vault_api import Vault
from helm import helm_bp
from helm.helm_bp import helm_bp_instance
from helm.helm_processor import HelmProcessor
from helm.helm_service import HelmService
from infra import infrastructure_bp
from infra.infrastructure_bp import infra_bp_instance
from infra.infrastructure_service import InfrastructureService

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://sys.stdout',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = FlaskAPI(__name__)
app.config['SWAGGER'] = {
    'title': 'Spinless API documentation',
}

swagger = Swagger(app, template_file='api_doc.yml')

app.config["VAULT_ADDR"] = os.getenv("VAULT_ADDR")
app.config["VAULT_ROLE"] = os.getenv("VAULT_ROLE")
app.config["VAULT_SECRETS_PATH"] = os.getenv("VAULT_SECRETS_PATH")

infrastructure_service = None


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


@app.route("/accounts", methods=['POST'], strict_slashes=False)
@requires_auth
def create_account():
    data = request.get_json()
    account_name = data.get("name") or abort(400, Response("Give 'name'"))
    requires_account(account_name)

    aws_access_key = data.get("aws_access_key") or abort(400, Response("Give aws_access_key"))
    aws_secret_key = data.get("aws_secret_key") or abort(400, Response("Give aws_secret_key"))
    app.logger.info(f"Request for creating account with name='{account_name}'")
    return infrastructure_service.create_account(app.logger, account_name, aws_access_key, aws_secret_key)


@app.route("/token", methods=['POST'], strict_slashes=False)
def get_token_api():
    return get_token(request.get_json())


if __name__ == '__main__':
    vault = Vault(app.logger)
    vault_conf = vault.read(f"{vault.base_path}/common")["data"]
    auth_conf = {
        "auth0_client_id": vault_conf["auth0_client_id"],
        "auth0_client_identifier": vault_conf["auth0_client_identifier"],
        "auth0_client_secret": vault_conf["auth0_client_secret"],
        "auth0_domain": vault_conf["auth0_domain"]
    }
    authentication.auth_config = auth_conf

    # initialize helm service
    manager = multiprocessing.Manager()
    helm_results = manager.dict()
    helm_processor = HelmProcessor(manager.Queue(), helm_results, app.logger)
    helm_processor.start()

    helm_bp.helm_service = HelmService(helm_results, helm_processor)
    infrastructure_service = InfrastructureService(app.logger)
    infrastructure_bp.service = infrastructure_service

    app.register_blueprint(helm_bp_instance)
    app.register_blueprint(infra_bp_instance)
    app.run(host='0.0.0.0')
