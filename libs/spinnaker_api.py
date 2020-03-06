import subprocess
from flask import Flask, request



app = Flask(__name__)


class SpinnakerPipeline:
    def __init__(self, data):
        self.data = data

    def pipeline_create(self):
        app.logger.info("Request to pipeline_create is {}".format(self.data))
        application = "{}-{}".format(self.data["owner"], self.data["repo"])
        pipeline_name = "deploy"
        cmd = "spin application save"
        return {}

    def pipeline_deploy(self):
        app.logger.info("Request to pipeline_deploy {}".format(self.data))
        repo = self.data['repo']
        return { "eventId" :"" }

    def pipeline_cancel(self):
        app.logger.info("Request to pipeline_cancel {}".format(self.data))
        application = "{}-{}".format(self.data["owner"], self.data["repo"])
        pipeline_id = self.data['id']
        return {}