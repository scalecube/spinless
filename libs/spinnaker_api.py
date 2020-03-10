import subprocess
import uuid
import time
from jinja2 import Environment, FileSystemLoader


class SpinnakerPipeline:
    def __init__(self, data, logger):
        self.logger = logger
        self.logger.info("SpinnakerPipeline init")
        self.data = data

    def application_create(self, application):
        with open("/opt/spinnaker/app.yaml", "w") as app_file:
            j2_env = Environment(loader=FileSystemLoader("/opt/spinnaker/templates/"))
            gen_template = j2_env.get_template(
                'app.j2').render(application_name=application)
            app_file.write(gen_template)
        proc = subprocess.Popen(["spin application save --file /opt/spinnaker/app.yaml"],
                                stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        self.logger.info("Creation of application output: {}".format(
            out.decode("utf-8") if out else None))
        self.logger.info("Creation of application error: {}".format(
            err.decode("utf-8") if err else None))
        return

    def create(self):
        self.logger.info("Request to pipeline_create is {}".format(self.data))
        owner = self.data["owner"]
        repo = self.data["repo"]
        application = "{}-{}".format(owner, repo)
        self.application_create(application)
        with open("/opt/spinnaker/deploy_pipeline.yaml", "w") as pipeline_file:
            j2_env = Environment(loader=FileSystemLoader("/opt/spinnaker/templates/"))
            gen_template = j2_env.get_template(
                'deploy_pipeline.j2').render(
                application=application,
                helm_package=application,
                repo_slug=repo,
                default_artifact_uuid=uuid.uuid1(),
                artifact_uuid=uuid.uuid1(),
                match_artifact_uuid=uuid.uuid1(),
                stages_default_artifact_uuid=uuid.uuid1(),
                stages_artifact_uuid=uuid.uuid1(),
                stages_match_artifact_uuid=uuid.uuid1())
            pipeline_file.write(gen_template)
        proc = subprocess.Popen(["spin pipeline save --file /opt/spinnaker/deploy_pipeline.yaml"],
                                stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        self.logger.info("Creation of deploy pipeline output: {}".format(
            out.decode("utf-8") if out else None))
        self.logger.info("Creation of deploy pipeline error: {}".format(
            err.decode("utf-8") if err else None))
        return

    def deploy(self):
        self.logger.info("Request to pipeline_deploy is {}".format(self.data))
        timestamp = str(round(time.time() * 100))
        params_file = "/opt/spinnaker/params-{}.json".format(timestamp)
        namespace = self.data["namespace"]
        application = "{}-{}".format(self.data["namespace"], self.data["repo"])
        with open(params_file, "w") as params_file_w:
            j2_env = Environment(loader=FileSystemLoader("/opt/spinnaker/templates/"))
            gen_template = j2_env.get_template(
                'params.j2').render(namespace=namespace)
            params_file_w.write(gen_template)
        proc = subprocess.Popen(
            "spin pipeline execute --name deploy --application {}".format(
                application
            ))
        (out, err) = proc.communicate()
        self.logger.info("Execution of deploy pipeline output: {}".format(
            out.decode("utf-8") if out else None))
        self.logger.info("Execution of deploy pipeline error: {}".format(
            err.decode("utf-8") if err else None))
        return {"eventId":""}

    def cancel(self):
        # app.logger.info("Request to pipeline_cancel {}".format(self.data))
        application = "{}-{}".format(self.data["owner"], self.data["repo"])
        pipeline_id = self.data['id']
        return {}