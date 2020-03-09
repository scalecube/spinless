import sys
import subprocess
import logging
from jinja2 import Environment, FileSystemLoader


log = logging.getLogger('spinnaker_api')
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
log.addHandler(handler)
log.setLevel(logging.INFO)


class SpinnakerPipeline:
    def __init__(self, data):
        log.info("SpinnakerPipeline init")
        self.data = data

    def application_create(self, application_name):
        with open("/opt/spinnaker/app.yaml", "w") as chart_file:
            j2_env = Environment(loader=FileSystemLoader("/opt/spinnaker/templates/"))
            gen_template = j2_env.get_template(
                'app_template.j2').render(application_name=application_name)
            chart_file.write(gen_template)
        proc = subprocess.Popen(["spin application save --file /opt/spinnaker/app.yaml"],
                                stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        log.info("Creation of application output: {}".format(out))
        log.info("Creation of application error: {}".format(err))
        return

    def pipeline_create(self):
        # app.logger.info("Request to pipeline_create is {}".format(self.data))
        application = "{}-{}".format(self.data["owner"], self.data["repo"])
        pipeline_name = "deploy"
        self.application_create(application)

        return {}

    def pipeline_deploy(self):
        # app.logger.info("Request to pipeline_deploy {}".format(self.data))
        repo = self.data['repo']
        return {"eventId":""}

    def pipeline_cancel(self):
        # app.logger.info("Request to pipeline_cancel {}".format(self.data))
        application = "{}-{}".format(self.data["owner"], self.data["repo"])
        pipeline_id = self.data['id']
        return {}