from libs.job_api import JobState
from libs.log_api import JobLogger
from libs.helm_api import Helm


def helm_deploy(ctx):
    data = ctx.data
    logger = JobLogger(data['owner'], data['repo'], ctx.id)
    logger.emit(JobState.RUNNING.name, "starting deploying to kubernetes namespace: {}".format(data.get("namespace")))
    logger.emit(JobState.RUNNING.name, "starting deploy")

    posted_env = {'sha': data['sha'], 'issue_number': data['issue_number']}
    helm = Helm(
        logger=data["logger"],
        owner=data["owner"],
        repo=data["repo"],
        version=data["branch_name"],
        posted_env=posted_env
    )
    helm.install_package()

    logger.emit(JobState.RUNNING.name, "OK doing installl")
    logger.emit(JobState.SUCCESS.name, "deployed successfully")
    # logger.emit(JobState.FAILED.name, "failed to deploy")
    # logger.end()

    logger.end()
