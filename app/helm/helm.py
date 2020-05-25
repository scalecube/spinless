from flask import current_app as app, Blueprint
from flask import request, jsonify, Response, abort

# Blueprint Configuration
from common.job_api import create_job, cancel_job, get_job_status
from common.log_api import tail_f
from helm.helm_service import helm_deploy

helm = Blueprint(name='helm', import_name=__name__, url_prefix="/helm/deploy")


@helm.route('/', methods=['POST'])
def helm_deploy_start():
    data = request.get_json()
    if not data:
        return abort(400, Response("Give some payload: [cmd (no-op) / owner (no_owner) / repo (no-repo)]"))
    app.logger.info(f'Request to CI/CD is {data}')
    job = create_job(helm_deploy, app.logger, data).start()
    return jsonify({'id': job.job_id})


@helm.route('/<job_id>')
def get_log_api(job_id):
    app.logger.info(f'Request to get_log  is {job_id}')
    if not job_id:
        return abort(400, Response("No job id provided"))
    return Response(tail_f(job_id))


@helm.route('/cancel/<job_id>')
def helm_deploy_cancel(job_id):
    app.logger.info(f'Request to cancel {job_id}')
    if not job_id:
        return jsonify({"message": "Provide 'job_id' field."})
    if cancel_job(job_id):
        return jsonify({"message": f'Canceled job {job_id}', "id": job_id})
    return jsonify({"message": f'Job {job_id} was not running'})


@helm.route('/status/<job_id>')
def helm_deploy_status(job_id):
    app.logger.info(f'Request to status is {job_id}')
    if not job_id:
        return abort(400, Response("No job id provided"))
    return get_job_status(job_id)
