from flask import Flask, request, jsonify

from logging.config import dictConfig
from libs.spinnaker_api import pipeline_create, pipeline_deploy, pipeline_cancel

app = Flask(__name__)

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

@app.route('/')
def main():
    return "Yes i am still here, thanks for asking."

@app.route('/pipelines', methods=['POST'])
def pipelines():
    data = request.get_json()
    app.logger.info("Request to CICD is {}".format(data))

    if data["action_type"] == 'deploy':
        event = pipeline_deploy(data)
        return jsonify(event)

    elif data["action_type"] == 'install':
        pipeline_create(data)
        return jsonify({})

    elif data["action_type"] == 'cancel':
        pipeline_cancel(data)
        return jsonify({})

    return jsonify({})

@app.route('/namespaces', methods=['GET'])
def namespaces():
    data = request.get_json()
    app.logger.info("Request to list namespaces is {}".format(data))
    repo_name = data['repo_name']
    return jsonify({})

if __name__ == '__main__':
    app.run(host='0.0.0.0')
