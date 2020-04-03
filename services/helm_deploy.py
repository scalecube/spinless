from libs.helm_api import Helm
from libs.registry_api import RegistryApi
from libs.vault_api import Vault


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


def __parse_reg_from_data(data, reg_type):
    """Return { "docker/helm", "name" : registry_name"};
        default registry name should be "default"
        """
    res = {"type": reg_type, "name": data.get("registry", {}).get(reg_type, "default")}
    return res


def __prepare_regs(data, registry_api):
    helm_reg = registry_api.get_reg(__parse_reg_from_data(data, "helm"))
    docker_reg = registry_api.get_reg(__parse_reg_from_data(data, "docker"))
    registries = {"helm": helm_reg, "docker": docker_reg}
    return registries


def helm_deploy(job_ref, applogger):
    try:
        data = job_ref.data
        job_ref.emit("RUNNING", "start helm deploy to kubernetes namespace: {}".format(data.get("namespace")))
        posted_env = create_posted_env(data)

        vault = Vault(logger=applogger)
        registry_api = RegistryApi(vault, applogger)
        registries = __prepare_regs(data, registry_api)
        helm = Helm(
            logger=applogger,
            owner=data["owner"],
            repo=data["repo"],
            version=data["branch_name"],
            posted_env=posted_env,
            registries=registries
        )
        helm.install_package()

        job_ref.emit("SUCCESS", "finished. helm deployed successfully")
        job_ref.complete_succ()
    except Exception as ex:
        job_ref.emit("ERROR", "failed to deploy reason {}".format(ex))
        job_ref.complete_err()
