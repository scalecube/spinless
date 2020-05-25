import os
from logging.config import dictConfig

from dotenv import load_dotenv
from flask import request, Response, abort
from flask_api import FlaskAPI

from helm import helm
from infra.cloud_service import create_cloud_secret
from infra.infra import infra

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


@app.route("/secrets/cloud", methods=['POST'])
def create_aws_secret():
    data = request.get_json()
    secret_name = data.get("secret_name") or abort(400, Response("Give secret_name"))
    aws_access_key = data.get("aws_access_key") or abort(400, Response("Give aws_access_key"))
    aws_secret_key = data.get("aws_secret_key") or abort(400, Response("Give aws_secret_key"))
    app.logger.info(f"Request for creating secret with '{secret_name}' name")
    return create_cloud_secret(app.logger, secret_name, aws_access_key, aws_secret_key)


app.register_blueprint(helm)
app.register_blueprint(infra)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
