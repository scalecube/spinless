#
# Cluster api
#
from flask import current_app as app, Blueprint
from flask import request, jsonify, Response, abort

from common.job_api import create_job
from infra.infrastructure_service import *

RESERVED_CLUSTERS = {"dev-exchange", "dev-ops", "dev-exchange", "nebula", "uat-exchange", "uat-ops"}
RESERVED_NAMESPACES = {"master", "develop"}

infra = Blueprint(name='infra', import_name=__name__, url_prefix="/new-clusters")


@infra.route("/", methods=['GET'], strict_slashes=False)
def get_clusters_api():
    app.logger.info(f"Request to list cluster")
    return list_clusters(app.logger)


@infra.route("/", methods=['POST'], strict_slashes=False)
def create_cluster_api():
    app.logger.info(f"Request to create cluster is {request}")
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    app.logger.info("Request create cluster is {}".format(data))
    job = create_job(create_cluster, app.logger, data).start()
    return jsonify({'id': job.job_id})


@infra.route("/<cluster_name>", methods=['DELETE'], strict_slashes=False)
def kubernetes_cluster_destroy(cluster_name):
    if cluster_name in RESERVED_CLUSTERS:
        return abort(400, Response("Please don't remove this cluster: {}".format(cluster_name)))
    app.logger.info(f"Request to destroy cluster {cluster_name}")
    job = create_job(destroy_cluster, app.logger, {"cluster_name": cluster_name}).start()
    return jsonify({'id': job.job_id})


@infra.route("/<cluster_name>/namespaces", methods=['GET'], strict_slashes=False)
def kubernetes_list_ns(cluster_name):
    app.logger.info(f"Request get namespaces for cluster {cluster_name}")
    return jsonify(get_namespaces(cluster_name, app.logger))


@infra.route("/<cluster_name>/namespaces/<namespace>", methods=['DELETE'], strict_slashes=False)
def kubernetes_delete_ns(cluster_name, namespace):
    app.logger.info(f"Request to delete namespace {namespace} in {cluster_name}")
    if any(namespace.startswith(br) for br in RESERVED_NAMESPACES):
        return abort(400, Response(f"Namespace {namespace} is reserved and can't be deleted"))
    return jsonify(delete_namespace(cluster_name, namespace, app.logger))
