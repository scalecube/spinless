from libs.registry_api import RegistryApi


def create_registry(logger, data):
    reg_api = RegistryApi(logger)
    return reg_api.save_reg(data)


def get_registry(logger, kctx_id):
    reg_api = RegistryApi(logger)
    code, result = reg_api.get_reg(kctx_id)
    if code ==0:
        result.pop("password")
    return result


def delete_registry(logger, kctx_id):
    reg_api = RegistryApi(logger)
    return reg_api.delete_reg(kctx_id)
