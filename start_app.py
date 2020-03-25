import os
import threading
import time

from flask import Flask, request, jsonify, Response
from logging.config import dictConfig
from libs.vault_api import Vault
from libs.helm_api import Helm
from libs.task_logs import JobContext, tail_f

ERROR = "ERROR"

SUCCESS = "SUCCESS"
RUNNING = "RUNNING"

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


@app.route('/kubernetes/deploy', methods=['POST'])
def pipelines():
    data = request.get_json()
    app.logger.info("Request to CICD is {}".format(data))

    action_type = data.get("action_type", None)
    if action_type:
        if action_type == "deploy":
            ctx = JobContext(execute_job, data).start()

        elif action_type == 'cancel':
            JobContext.cancel(data.get("id"))
            return

    return jsonify({'id': str(ctx.id) })


def execute_job(ctx, data):
    try:
        ctx.update_status(RUNNING, "starting deploying to kubernetes namespace: {}".format(data.get("namespace")))
        vault = Vault(logger=app.logger,
                      root_path="secretv2",
                      vault_server=app.config["VAULT_ADDR"],
                      service_role=app.config["VAULT_ROLE"],
                      owner=data.get("owner"),
                      repo_slug=data.get("repo"),
                      version=data.get("version"),
                      vault_secrets_path=app.config["VAULT_SECRETS_PATH"])
        service_account = vault.app_path
        spinless_app_env = vault.get_self_app_env()
        vault.create_role()
        env = vault.get_env("env")
        # TODO: add env to helm and install
    except OSError:
        ctx.update_status(ERROR, "failed to deploy {}".format(data.get("namespace")))
        ctx.end()
    else:
        ctx.update_status(SUCCESS, "completed successfully the deployment of {}".format(data.get("namespace")))
        ctx.end()


@app.route('/status/<owner>/<repo>/<log_id>')
def log(owner, repo, log_id):
    file = '{}/{}/{}.log'.format(owner, repo, log_id)
    return Response(tail_f(file, 1.0), mimetype='text/plain')


@app.route('/namespaces', methods=['GET'])
def namespaces():
    data = request.get_json()
    app.logger.info("Request to list namespaces is {}".format(data))
    repo_name = data['repo_name']
    return jsonify({})


if __name__ == '__main__':
    app.run(host='0.0.0.0')
