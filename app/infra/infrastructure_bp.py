#
# Resources api
#
from flask import current_app as app, Blueprint
from flask import request, jsonify, Response, abort

from common.authentication import requires_account, requires_auth, requires_scope
from common.job_api import create_job

RESOURCE_READ_SCOPE = "read:resources"
RESOURCE_ADMIN_SCOPE = "admin:resources"

RESERVED_NAMESPACES = {"master", "develop"}

infra_bp_instance = Blueprint(name='infra', import_name=__name__, url_prefix="/resources")
service = None


@infra_bp_instance.route("/<resource_type>", methods=['GET'], strict_slashes=False)
@requires_auth
def get_clusters_api(resource_type):
    if resource_type != 'cluster':
        return abort(400, Response("Only 'cluster' resource type is supported"))
    requires_scope(RESOURCE_READ_SCOPE)
    app.logger.info(f"Request to list {resource_type}-s")
    return service.list_clusters(app.logger)


@infra_bp_instance.route("/", methods=['POST'], strict_slashes=False)
@requires_auth
def create_resource_api():
    app.logger.info(f"Request to create resource is {request}")
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    app.logger.info(f"Request create resource is {data}")
    account = data.get('account')
    requires_scope(RESOURCE_ADMIN_SCOPE)
    requires_account(account)

    job = create_job(service.create_resource, app.logger, data).start()
    return jsonify({'id': job.job_id})

# TODO: currently disabled
# @infra_bp_instance.route("/<name>", methods=['DELETE'], strict_slashes=False)
@requires_auth
def destroy_resource_api(name):
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    app.logger.info(f"Request to destroy resource {name}")

    account = data.get('account')
    requires_scope(RESOURCE_ADMIN_SCOPE)
    requires_account(account)

    data["name"] = name
    job = create_job(service.destroy_resource, app.logger, data).start()
    return jsonify({'id': job.job_id})


@infra_bp_instance.route("/<cluster_name>/namespaces", methods=['GET'], strict_slashes=False)
@requires_auth
def list_namespaces_api(cluster_name):
    app.logger.info(f"Request get namespaces for cluster {cluster_name}")
    requires_scope(RESOURCE_READ_SCOPE)
    return jsonify(service.get_namespaces(cluster_name, app.logger))


@infra_bp_instance.route("/<cluster_name>/namespaces/<namespace>", methods=['DELETE'], strict_slashes=False)
@requires_auth
def delete_namespace_api(cluster_name, namespace):
    app.logger.info(f"Request to delete namespace {namespace} in {cluster_name}")
    requires_scope(RESOURCE_ADMIN_SCOPE)
    if any(namespace.startswith(br) for br in RESERVED_NAMESPACES):
        return abort(400, Response(f"Namespace {namespace} is reserved and can't be deleted"))
    return jsonify(service.delete_namespace(cluster_name, namespace, app.logger))
