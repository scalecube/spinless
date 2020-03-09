from flask import Flask, request, jsonify

from logging.config import dictConfig
from libs.spinnaker_api import SpinnakerPipeline

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
    action_type = data.get("action_type", None)
    if action_type:
        pipeline = SpinnakerPipeline(data, app.logger)
        if action_type == "install":
            pipeline.pipeline_create()
        elif action_type == "uninstall":
            #pipeline.pipeline_delete()
            app.logger.info("TODO: Delete the pipeline")
        elif action_type == "deploy":
            pipeline.pipeline_deploy()
        elif action_type == 'cancel':
            pipeline.pipeline_cancel()
    app.logger.info("Request to CICD is {}".format(data))
    return jsonify({})


@app.route('/namespaces', methods=['GET'])
def namespaces():
    data = request.get_json()
    app.logger.info("Request to list namespaces is {}".format(data))
    repo_name = data['repo_name']
    return jsonify({})


if __name__ == '__main__':
    app.run(host='0.0.0.0')
