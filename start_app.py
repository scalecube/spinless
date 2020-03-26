import os
from logging.config import dictConfig

from flask import request, jsonify, Response
from flask_api import FlaskAPI

from libs.job_api import *
from libs.vault_api import Vault

DEPLOY_ACTION = "deploy"
# WIN_CMD = "FOR /L %v IN (0,0,0) DO echo %TIME% && ping localhost -n 3 > nul"
CMD = "ping google.com"

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


@app.route('/example/')
def example():
    return {'hello': 'world'}


@app.route('/')
def main():
    return "Yes i am still here, thanks for asking."


@app.route('/jobs/create', methods=['POST'])
def create_job_api():
    app.logger.info("Requested to start job. Starting.")
    log_id = create_job(CMD)
    return {"log_id": log_id}


@app.route('/jobs/get/<job_id>', methods=['GET'])
def get_job_api(job_id):
    app.logger.info("Request to get_log  is {}".format(job_id))
    if not job_id:
        return "No log id provided"
    return Response(get_job_log(job_id), mimetype='text/plain')


@app.route('/jobs/status/<job_id>', methods=['GET'])
def get_job_status_api(job_id):
    app.logger.info("Request to get_log  is {}".format(job_id))
    if not job_id:
        return "No log id provided"
    return Response(get_job_status(job_id), mimetype='text/plain')


@app.route('/jobs/cancel/<job_id>', methods=['GET'])
def cancel_job_api(job_id):
    app.logger.info("Request to get_log is {}".format(job_id))
    if not job_id:
        return "No job id provided"
    if cancel_job(job_id):
        return Response("Stopped job {}".format(job_id), mimetype='text/plain')
    else:
        return Response("Job {} was not running".format(job_id), mimetype='text/plain')


@app.route('/kubernetes/deploy', methods=['POST'])
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
                          repo_slug=data.get("repo"),
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
