from libs.job_api import JobState
from libs.log_api import JobLogger
from libs.helm_api import Helm


def create_posted_env(data):
    posted_env = {
        'OWNER': data.get("owner", "no_owner"),
        'REPO': data.get("repo", "no_repo"),
        'BRANCH_NAME': data.get("branch_name", "no_branch_name"),
        'SHA': data.get("sha", "no_sha"),
        'PR': data.get("issue_number", "no_issue_number"),
        'NAMESPACE': data.get("namespace", "no_namespace")
    }
    return posted_env


def helm_deploy(ctx, logger):
    data = ctx.data
    logger = JobLogger(data['owner'], data['repo'], ctx.id)
    logger.emit(JobState.RUNNING, "starting deploying to kubernetes namespace: {}".format(data.get("namespace")))
    logger.emit(JobState.RUNNING, "starting deploy")

    posted_env = create_posted_env(data)
    helm = Helm(
        logger=logger,
        owner=data["owner"],
        repo=data["repo"],
        version=data["branch_name"],
        posted_env=posted_env
    )
    helm.install_package()

    logger.emit(JobState.RUNNING, "OK doing installl")
    logger.emit(JobState.SUCCESS, "deployed successfully")
    # logger.emit(JobState.FAILED.name, "failed to deploy")
    # logger.end()

    logger.end()
