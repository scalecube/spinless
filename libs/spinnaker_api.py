from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

app = Flask(__name__)

def pipeline_create(data):
    app.logger.info("Request to pipeline_create is {}".format(data))
    application =  "{}-{}".format(data["owner"], data["repo"])
    pipeline_name = "{}-{}-deploy".format(data["owner"], data["repo"])
    return {}

def pipeline_deploy(data):
    app.logger.info("Request topipeline_deploy {}".format(data))
    repo = data['repo']
    return { "eventId" :"905de160be1c84e65dda76f4aaac557d861a5e4f" }

def pipeline_cancel(data):
    app.logger.info("Request to pipeline_cancel {}".format(data))
    application =  "{}-{}".format(data["owner"], data["repo"])
    pipeline_id = data['id']
    return {}
