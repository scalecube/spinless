import multiprocessing
import os
from logging.config import dictConfig

from dotenv import load_dotenv
from flask import request, Response, abort
from flask_api import FlaskAPI

from helm import helm_bp
from helm.helm_bp import helm_bp_instance
from helm.helm_processor import HelmProcessor
from helm.helm_service import HelmService
from infra import infrastructure_bp
from infra.infrastructure_bp import infra_bp_instance
from infra.infrastructure_service import InfrastructureService

load_dotenv()
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
app = FlaskAPI(__name__)
app.config["VAULT_ADDR"] = os.getenv("VAULT_ADDR")
app.config["VAULT_ROLE"] = os.getenv("VAULT_ROLE")
app.config["VAULT_SECRETS_PATH"] = os.getenv("VAULT_SECRETS_PATH")

infrastructure_service = None


@app.route("/secrets/cloud", methods=['POST'], strict_slashes=False)
def create_aws_secret():
    data = request.get_json()
    secret_name = data.get("secret_name") or abort(400, Response("Give secret_name"))
    aws_access_key = data.get("aws_access_key") or abort(400, Response("Give aws_access_key"))
    aws_secret_key = data.get("aws_secret_key") or abort(400, Response("Give aws_secret_key"))
    app.logger.info(f"Request for creating secret with '{secret_name}' name")
    return infrastructure_service.create_cloud_secret(app.logger, secret_name, aws_access_key, aws_secret_key)


if __name__ == '__main__':
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
