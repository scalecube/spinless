#
# Cluster api
#
from flask import current_app as app, Blueprint
from flask import request, jsonify, Response, abort

from common.job_api import create_job

RESERVED_CLUSTERS = {"dev-exchange", "dev-ops", "dev-exchange", "nebula", "uat-exchange", "uat-ops"}
RESERVED_NAMESPACES = {"master", "develop"}

infra_bp_instance = Blueprint(name='infra', import_name=__name__, url_prefix="/clusters")
service = None


@infra_bp_instance.route("/", methods=['GET'], strict_slashes=False)
def get_clusters_api():
    app.logger.info(f"Request to list cluster")
    return service.list_clusters(app.logger)


@infra_bp_instance.route("/", methods=['POST'], strict_slashes=False)
def create_cluster_api():
    app.logger.info(f"Request to create cluster is {request}")
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    app.logger.info(f"Request create cluster is {data}")
    job = create_job(service.create_cluster, app.logger, data).start()
    return jsonify({'id': job.job_id})


@infra_bp_instance.route("/<cluster_name>", methods=['DELETE'], strict_slashes=False)
def destroy_cluster_api(cluster_name):
    if cluster_name in RESERVED_CLUSTERS:
        return abort(400, Response("Please don't remove this cluster: {}".format(cluster_name)))
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    app.logger.info(f"Request to destroy cluster {cluster_name}")
    data["cluster_name"] = cluster_name
    job = create_job(service.destroy_cluster, app.logger, data).start()
    return jsonify({'id': job.job_id})


@infra_bp_instance.route("/<cluster_name>/namespaces", methods=['GET'], strict_slashes=False)
def list_namespaces_api(cluster_name):
    app.logger.info(f"Request get namespaces for cluster {cluster_name}")
    return jsonify(service.get_namespaces(cluster_name, app.logger))


@infra_bp_instance.route("/<cluster_name>/namespaces/<namespace>", methods=['DELETE'], strict_slashes=False)
def delete_namespace_api(cluster_name, namespace):
    app.logger.info(f"Request to delete namespace {namespace} in {cluster_name}")
    if any(namespace.startswith(br) for br in RESERVED_NAMESPACES):
        return abort(400, Response(f"Namespace {namespace} is reserved and can't be deleted"))
    return jsonify(service.delete_namespace(cluster_name, namespace, app.logger))
