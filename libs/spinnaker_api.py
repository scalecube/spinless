import os
from app.github import Github
from dotenv import load_dotenv

load_dotenv()

def pipeline_create():
    data = request.get_json()
    app.logger.info("Request to pipeline_create is {}".format(data))
    application =  "{}-{}".format(data["owner"], data["repo"])
    pipeline_name = "{}-{}-deploy".format(data["owner"], data["repo"])
    return jsonify({})

def pipeline_deploy():
    data = request.get_json()
    app.logger.info("Request topipeline_deploy {}".format(data))
    repo = data['repo']
    return jsonify({})

def pipeline_cancel():
    data = request.get_json()
    app.logger.info("Request to pipeline_cancel {}".format(data))
    application =  "{}-{}".format(data["owner"], data["repo"])
    pipeline_id = data['id']
    return jsonify({})
