import os
from flask import Flask, request, jsonify
from logging.config import dictConfig
from libs.vault_api import Vault


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

app = Flask(__name__)
app.config["VAULT_ADDR"] = os.getenv("VAULT_ADDR")
app.config["VAULT_ROLE"] = os.getenv("VAULT_ROLE")
app.config["VAULT_SECRETS_PATH"] = os.getenv("VAULT_SECRETS_PATH")


@app.route('/')
def main():
    return "Yes i am still here, thanks for asking."


@app.route('/pipelines', methods=['POST'])
def pipelines():
    data = request.get_json()
    app.logger.info("Request to CICD is {}".format(data))
    action_type = data.get("action_type", None)
    if action_type:
        if action_type == "deploy":
            vault = Vault(logger=app.logger,
                          root_path="secretv2",
                          vault_server=app.config["VAULT_ADDR"],
                          service_role=app.config["VAULT_ROLE"],
                          owner=data.get("owner"),
                          repo_slug=data.get("repo_slug"),
                          version=data.get("version"),
                          vault_secrets_path=app.config["VAULT_SECRETS_PATH"])
            service_account = vault.app_path
            spinless_app_env = vault.get_self_app_env()
            vault.create_role()
            env = vault.get_env("env")
            # TODO: add env to helm and install
            return
        elif action_type == 'cancel':
            return
    return jsonify({})


@app.route('/pipeline/<pipeline_id>', methods=['GET'])
def pipeline_status(pipeline_id):
    pipeline_status = ''
    return jsonify(pipeline_status)


@app.route('/namespaces', methods=['GET'])
def namespaces():
    data = request.get_json()
    app.logger.info("Request to list namespaces is {}".format(data))
    repo_name = data['repo_name']
    return jsonify({})


if __name__ == '__main__':
    app.run(host='0.0.0.0')