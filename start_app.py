from logging.config import dictConfig

from dotenv import load_dotenv
from flask import request, jsonify, Response, abort
from flask_api import FlaskAPI

from libs.job_api import *
from services.cloud_service import *
from services.helm_deploy import helm_deploy
from services.kctx_service import *
from services.kuber_service import kube_cluster_create
from services.registry_service import *

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
def helm_deploy_start():
    data = request.get_json()
    if not data:
        return abort(Response("Give some payload: [cmd (no-op) / owner (no_owner) / repo (no-repo)]"))
    app.logger.info("Request to CI/CD is {}".format(data))
    job = create_job(helm_deploy, app.logger, data).start()

    return jsonify({'id': job.job_id})


@app.route('/helm/deploy/<owner>/<repo>/<job_id>')
def get_log_api(owner, repo, job_id):
    app.logger.info("Request to get_log  is {}".format(job_id))
    if not job_id:
        return abort(Response("No job id provided"))
    return Response(tail_f(owner, repo, job_id))


@app.route('/helm/deploy/cancel/<job_id>')
def helm_deploy_cancel(job_id):
    app.logger.info("Request to cancel {}".format(job_id))
    if not job_id:
        return jsonify({"message": "Provide 'job_id' field."})
    if cancel_job(job_id):
        return jsonify({"message": "Canceled job {}".format(job_id), "id": job_id})
    return jsonify({"message": "Job {} was not running".format(job_id)})


@app.route('/helm/deploy/status/<job_id>')
def helm_deploy_status(job_id):
    app.logger.info("Request to status is {}".format(job_id))
    if not job_id:
        return abort(400, Response("No job id provided"))
    return get_job_status(job_id)


@app.route('/artifact/registries/<type>/<name>', methods=['POST'])
def artifact_registries_create(type, name):
    data = request.get_json()
    if not data:
        return abort(Response("No payload"))
    data["type"] = type
    data["name"] = name
    app.logger.info("Request to create  repository  is {}/{}".format(type, name))
    result = create_registry(app.logger, data)
    return result


@app.route('/artifact/registries/<type>/<name>')
def artifact_registries_get(type, name):
    data = dict({"type": type, "name": name})
    app.logger.info("Request to get  repository  is {}".format(data))
    return get_registry(app.logger, data)


@app.route('/artifact/registries/<type>/<name>', methods=['DELETE'])
def artifact_registries_delete(type, name):
    data = dict({"type": type, "name": name})
    app.logger.info("Request to delete  repository  is {}".format(data))
    return delete_registry(app.logger, data)


#
# Kubernetes context CRUD
#
@app.route('/kubernetes/contexts/<name>', methods=['POST'])
def kubernetes_context_create(name):
    data = request.get_json()
    if not data:
        return abort(Response("No payload"))
    data["name"] = name
    app.logger.info("Request to create  kubernetes contexts  is {}".format(name))
    result = create_kubernetes_context(app.logger, data)
    return result


@app.route('/kubernetes/contexts/<name>')
def kubernetes_context_get(name):
    app.logger.info("Request to get  kubernetes contexts  is \"{}\"".format(name))
    return get_kubernetes_context(app.logger, name)


@app.route('/kubernetes/contexts/<name>', methods=['DELETE'])
def kubernetes_context_delete(name):
    app.logger.info("Request to delete  kubernetes contexts  is \"{}\"".format(name))
    return delete_kubernetes_context(app.logger, name)


#
# Cloud providers CRUD
#
@app.route('/cloud/providers/<provider_type>/<name>', methods=['POST'])
def create_cloud_provider_api(provider_type, name):
    data = request.get_json()
    if not data:
        return abort(Response("No payload"))
    data["name"] = name
    data["type"] = provider_type
    app.logger.info("Request to create  cloud provider  is {}/{}".format(provider_type, name))
    result = create_cloud_provider(app.logger, data)
    return result


@app.route('/cloud/providers/<provider_type>/<name>')
def get_cloud_provider_api(provider_type, name):
    app.logger.info("Request to get  cloud provider  is \"{}/{}\"".format(provider_type, name))
    return get_cloud_provider(app.logger, {"type": provider_type, "name": name})


@app.route('/cloud/providers/<provider_type>')
def get_cloud_provider_default_api(provider_type):
    app.logger.info("Request to get  cloud provider  is \"{}\"".format(provider_type))
    return get_cloud_provider(app.logger, {"type": provider_type})


@app.route('/cloud/providers/<provider_type>/<name>', methods=['DELETE'])
def delete_cloud_provider_api(provider_type, name):
    app.logger.info("Request to delete  cloud provider  is \"{}/{}\"".format(provider_type, name))
    return delete_cloud_provider(app.logger, provider_type, name)


#
# Create cluster api
#
@app.route("/kubernetes/create", methods=['POST'])
def kubernetes_cluster_create():
    data = request.get_json()
    if not data:
        return abort(Response("Give some payload"))
    app.logger.info("Request create cluster is {}".format(data))
    job = create_job(kube_cluster_create, app.logger, data).start()
    return jsonify({'id': job.job_id})


if __name__ == '__main__':
    app.run(host='0.0.0.0')
