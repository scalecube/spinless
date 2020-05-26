#
# Cluster api
#
from flask import current_app as app, Blueprint
from flask import request, jsonify, Response, abort

from common.job_api import create_job
from infra.cloud_service import create_cloud_provider
from infra.kctx_service import list_clusters
from infra.kuber_service import kube_cluster_create, kube_cluster_delete, delete_ns, get_ns

RESERVED_CLUSTERS = {"exberry-cloud", "exberry-demo"}
RESERVED_NAMESPACES = {"master", "develop"}


infra = Blueprint(name='infra', import_name=__name__, url_prefix="/clusters")


@infra.route("/", methods=['GET', 'POST'], strict_slashes=False)
def infra_route():
    app.logger.info(f"Request to /clusters is {request['method']}")
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return abort(400, Response("Give some payload"))
        app.logger.info("Request create cluster is {}".format(data))
        job = create_job(kube_cluster_create, app.logger, data).start()
        return jsonify({'id': job.job_id})
    app.logger.info("Request to list clusters")
    return list_clusters(app.logger)


@infra.route("/<cluster_name>", methods=['DELETE'])
def kubernetes_cluster_destroy(cluster_name):
    if cluster_name in RESERVED_CLUSTERS:
        return abort(400, Response("Please don't remove this cluster: {}".format(cluster_name)))
    app.logger.info(f"Request to destroy cluster {cluster_name}")
    job = create_job(kube_cluster_delete, app.logger, {"cluster_name": cluster_name}).start()
    return jsonify({'id': job.job_id})


@infra.route("/<cluster_name>/namespaces", methods=['GET'])
def kubernetes_list_ns(cluster_name):
    app.logger.info(f"Request get namespaces for cluster {cluster_name}")
    return jsonify(get_ns(cluster_name, app.logger))


@infra.route("/<cluster_name>/namespaces/<namespace>", methods=['DELETE'])
def kubernetes_delete_ns(cluster_name, namespace):
    app.logger.info(f"Request to delete namespace {namespace} in {cluster_name}")
    if any(namespace.startswith(br) for br in RESERVED_NAMESPACES):
        return abort(400, Response(f"Namespace {namespace} is reserved and can't be deleted"))
    return jsonify(delete_ns(cluster_name, namespace, app.logger))


#
# Cloud providers CRUD
#
@infra.route('/providers/<provider_type>/<name>', methods=['POST'])
def create_cloud_provider_api(provider_type, name):
    data = request.get_json()
    if not data:
        return abort(400, Response("No payload"))
    data["name"] = name
    data["type"] = provider_type
    app.logger.info("Request to create  cloud provider  is {}/{}".format(provider_type, name))
    result = create_cloud_provider(app.logger, data)
    return result
