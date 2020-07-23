from flask import current_app as app, Blueprint
from flask import request, jsonify, Response, abort

# Blueprint Configuration
from common.job_api import create_job, get_job_status
from common.log_api import tail_f

helm_bp_instance = Blueprint(name='helm', import_name=__name__, url_prefix="/helm")
helm_service = None

PROTECTED_NS = ('develop', 'develop-2', 'master', 'master-2')


@helm_bp_instance.route('/deploy', methods=['POST'], strict_slashes=False)
def helm_deploy_start():
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload: [cmd (no-op) / owner (no_owner) / repo (no-repo)]"))
    app.logger.info(f'Request to CI/CD is {data}')
    job = create_job(helm_service.helm_deploy, app.logger, data).start()
    return jsonify({'id': job.job_id})


@helm_bp_instance.route('/deploy/<job_id>', strict_slashes=False)
def get_log_api(job_id):
    app.logger.info(f'Request to get_log  is {job_id}')
    if not job_id:
        return abort(400, Response("No job id provided"))
    return Response(tail_f(job_id))


@helm_bp_instance.route('/deploy/status/<job_id>', strict_slashes=False)
def helm_deploy_status(job_id):
    app.logger.info(f'Request to status is {job_id}')
    if not job_id:
        return abort(400, Response("No job id provided"))
    return get_job_status(job_id)


@helm_bp_instance.route('/destroy', methods=['POST'], strict_slashes=False)
def destroy_env():
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    if not all(k in data for k in ("clusters", "namespace", "services")):
        return abort(400, Response('Not all mandatory fields provided: "clusters", "namespace", "services"'))
    if data['namespace'] in PROTECTED_NS:
        return abort(400, jsonify(error=f"Please, don't remove these env-s: {PROTECTED_NS}"))
    app.logger.info(f'Request to destroy namespace is {data}')
    job = create_job(helm_service.helm_destroy, app.logger, data).start()
    return jsonify({'id': job.job_id})


@helm_bp_instance.route('/list', methods=['POST'], strict_slashes=False)
def list_services():
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload"))
    if not all(k in data for k in ("clusters", "namespace")):
        return abort(400, Response('Not all mandatory fields provided: "clusters", "namespace"'))
    app.logger.info(f'Request to get service versions is {data}')
    result, err = helm_service.helm_list(data, app.logger)
    if err == 0:
        return jsonify(result)
    else:
        return jsonify({"error": result})
