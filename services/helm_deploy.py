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


def helm_deploy(job_ref, applogger):
    try:
        data = job_ref.data
        job_ref.emit("RUNNING", "start helm deploy to kubernetes namespace: {}".format(data.get("namespace")))

        posted_env = create_posted_env(data)
        helm = Helm(
            logger=applogger,
            owner=data["owner"],
            repo=data["repo"],
            version=data["branch_name"],
            posted_env=posted_env
        )
        helm.install_package()

        job_ref.emit("SUCCESS", "finished. helm deployed successfully")
        job_ref.complete_succ()
    except Exception as ex:
        job_ref.emit("ERROR", "failed to deploy reason {}".format(ex))
        job_ref.complete_err()

