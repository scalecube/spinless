import os
from flask import Flask, request, jsonify
from logging.config import dictConfig
from libs.spinnaker_api import SpinnakerPipeline


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

app = Flask(__name__)
app.config["SPINNAKER_API"] = os.getenv("SPINNAKER_API")
app.config["SPINNAKER_AUTH_TOKEN"] = os.getenv("SPINNAKER_AUTH_TOKEN")


@app.route('/')
def main():
    return "Yes i am still here, thanks for asking."


@app.route('/pipelines', methods=['POST'])
def pipelines():
    data = request.get_json()
    app.logger.info("Request to CICD is {}".format(data))
    action_type = data.get("action_type", None)
    if action_type:
        pipeline = SpinnakerPipeline(data, app.logger,
                                     app.config['SPINNAKER_API'],
                                     app.config["SPINNAKER_AUTH_TOKEN"])
        if action_type == "install":
            pipeline.create()
        elif action_type == "uninstall":
            #pipeline.delete()
            app.logger.info("TODO: Delete the pipeline")
        elif action_type == "deploy":
            return jsonify(pipeline.deploy())
        elif action_type == 'cancel':
            pipeline.cancel()
    return jsonify({})


@app.route('/pipeline/<pipeline_id>', methods=['GET'])
def pipeline_status(pipeline_id):
    data = {}
    pipeline = SpinnakerPipeline(data, app.logger,
                                 app.config['SPINNAKER_API'],
                                 app.config["SPINNAKER_AUTH_TOKEN"])
    spin_pipeline_status = pipeline.status(pipeline_id)
    return jsonify(spin_pipeline_status)


@app.route('/namespaces', methods=['GET'])
def namespaces():
    data = request.get_json()
    app.logger.info("Request to list namespaces is {}".format(data))
    repo_name = data['repo_name']
    return jsonify({})


if __name__ == '__main__':
    app.run(host='0.0.0.0')
