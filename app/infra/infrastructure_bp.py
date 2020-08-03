#
# Cluster api
#
from flask import current_app as app, Blueprint
from flask import request, jsonify, Response, abort

from common.authentication import requires_account, requires_auth, requires_scope
from common.job_api import create_job

CLUSTER_READ_SCOPE = "read:cluster"
CLUSTER_ADMIN_SCOPE = "admin:cluster"

RESERVED_CLUSTERS = {"dev-exchange", "dev-ops", "dev-exchange", "nebula", "uat-exchange", "uat-ops"}
RESERVED_NAMESPACES = {"master", "develop"}

infra_bp_instance = Blueprint(name='infra', import_name=__name__, url_prefix="/clusters")
service = None


@infra_bp_instance.route("/", methods=['GET'], strict_slashes=False)
@requires_auth
def get_clusters_api():
    requires_scope(CLUSTER_READ_SCOPE)
    app.logger.info(f"Request to list cluster")
    return service.list_clusters(app.logger)


@infra_bp_instance.route("/", methods=['POST'], strict_slashes=False)
@requires_auth
def create_cluster_api():
    app.logger.info(f"Request to create cluster is {request}")
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    app.logger.info(f"Request create cluster is {data}")
    secret_name = data.get('secret_name')
    requires_scope(CLUSTER_ADMIN_SCOPE)
    requires_account(secret_name)

    job = create_job(service.create_cluster, app.logger, data).start()
    return jsonify({'id': job.job_id})


@infra_bp_instance.route("/<cluster_name>", methods=['DELETE'], strict_slashes=False)
@requires_auth
def destroy_cluster_api(cluster_name):
    if cluster_name in RESERVED_CLUSTERS:
        return abort(400, Response(f"Please don't remove this cluster: {cluster_name}"))
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    app.logger.info(f"Request to destroy cluster {cluster_name}")

    secret_name = data.get('secret_name')
    requires_scope(CLUSTER_ADMIN_SCOPE)
    requires_account(secret_name)

    data["cluster_name"] = cluster_name
    job = create_job(service.destroy_cluster, app.logger, data).start()
    return jsonify({'id': job.job_id})


@infra_bp_instance.route("/<cluster_name>/namespaces", methods=['GET'], strict_slashes=False)
@requires_auth
def list_namespaces_api(cluster_name):
    app.logger.info(f"Request get namespaces for cluster {cluster_name}")
    requires_scope(CLUSTER_READ_SCOPE)
    return jsonify(service.get_namespaces(cluster_name, app.logger))


@infra_bp_instance.route("/<cluster_name>/namespaces/<namespace>", methods=['DELETE'], strict_slashes=False)
@requires_auth
def delete_namespace_api(cluster_name, namespace):
    app.logger.info(f"Request to delete namespace {namespace} in {cluster_name}")
    requires_scope(CLUSTER_ADMIN_SCOPE)
    if any(namespace.startswith(br) for br in RESERVED_NAMESPACES):
        return abort(400, Response(f"Namespace {namespace} is reserved and can't be deleted"))
    return jsonify(service.delete_namespace(cluster_name, namespace, app.logger))
