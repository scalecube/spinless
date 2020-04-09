from logging.config import dictConfig

from dotenv import load_dotenv
from flask import request, jsonify, Response, abort
from flask_api import FlaskAPI

from libs.job_api import *
from services.helm_deploy import helm_deploy
from services.kctx_service import *
from services.registry_service import *
from libs.infrastructure import TF

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


@app.route('/helm/deploy', methods=['POST'])
def kubernetes_deploy():
    data = request.get_json()
    if not data:
        return abort(Response("Give some payload: [cmd (no-op) / owner (no_owner) / repo (no-repo)]"))
    app.logger.info("Request to CI/CD is {}".format(data))
    job = create_job(helm_deploy, app.logger, data).start()

    return jsonify({'id': job.job_id})


@app.route('/helm/deploy/cancel/<job_id>')
def cancel(job_id):
    app.logger.info("Request to cancel {}".format(job_id))
    if not job_id:
        return jsonify({"message": "Provide 'job_id' field."})
    if cancel_job(job_id):
        return jsonify({"message": "Canceled job {}".format(job_id), "id": job_id})
    return jsonify({"message": "Job {} was not running".format(job_id)})


@app.route('/helm/deploy/status/<job_id>')
def status(job_id):
    app.logger.info("Request to status is {}".format(job_id))
    if not job_id:
        return abort(400, Response("No job id provided"))
    return get_job_status(job_id)


@app.route('/repositories/<type>/<name>', methods=['POST'])
def create_repo_api(type, name):
    data = request.get_json()
    if not data:
        return abort(Response("No payload"))
    data["type"] = type
    data["name"] = name
    app.logger.info("Request to create  repository  is {}".format(data))

    result = create_registry(app.logger, data)
    return result


@app.route('/repositories/<type>/<name>')
def get_repo_api(type, name):
    data = dict({"type": type, "name": name})
    app.logger.info("Request to get  repository  is {}".format(data))
    return get_registry(app.logger, data)


@app.route('/repositories/<type>/<name>', methods=['DELETE'])
def delete_repo_api(type, name):
    data = dict({"type": type, "name": name})
    app.logger.info("Request to delete  repository  is {}".format(data))
    return delete_registry(app.logger, data)


@app.route('/secrets/cloud', methods=['POST'])
def add_cloud_credentials():
    data = request.get_json()
    # TODO: vault write
    vault = Vault()
    return


@app.route('/kubernetes/contexts/<name>', methods=['POST'])
def create_kubernetes_context_api(name):
    data = request.get_json()
    if not data:
        return abort(Response("No payload"))
    data["name"] = name
    app.logger.info("Request to create  kubernetes contexts  is {}".format(data))
    result = create_kubernetes_context(app.logger, data)
    return result


@app.route('/kubernetes/contexts/<name>')
def get_kubernetes_context_api(name):
    app.logger.info("Request to get  kubernetes contexts  is \"{}\"".format(name))
    return get_kubernetes_context(app.logger, name)


@app.route('/kubernetes/contexts/<name>', methods=['DELETE'])
def delete_kubernetes_context_api(name):
    app.logger.info("Request to delete  kubernetes contexts  is \"{}\"".format(name))
    return delete_kubernetes_context(app.logger, name)

# Test
@app.route("/kubernetes/create", methods=['POST'])
def create_cluster():
    data = request.get_json()
    logger = app.logger
    workspace = data['workspace']
    aws_region = data["aws_region"]
    aws_access_key = data["aws_access_key"]
    aws_secret_key = data["aws_secret_key"]
    cluster_name = data["cluster_name"]
    az1 = data["az1"]
    az2 = data["az2"]
    kube_nodes_amount = data["kube_nodes_amount"]
    kube_nodes_instance_type = data["kube_nodes_instance_type"]
    tf = TF(logger=app.logger,
            workspace=data['workspace'],
            aws_region=data["aws_region"],
            aws_access_key=data["aws_access_key"],
            aws_secret_key=data["aws_secret_key"],
            cluster_name=data["cluster_name"],
            az1=data["az1"],
            az2=data["az2"],
            kube_nodes_amount=data["kube_nodes_amount"],
            kube_nodes_instance_type=data["kube_nodes_instance_type"])
    tf.install_kube()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
