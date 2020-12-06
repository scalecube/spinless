import base64
import os
import shlex
import time

import boto3
import yaml
from jinja2 import Environment, FileSystemLoader

from common.shell import shell_await, shell_run
from common.vault_api import Vault

VAULT_AUTH = "vault-auth"

STATUS_OK_ = {"status": "OK"}
DEFAULT_K8S_CTX_ID = "default"
K8S_CTX_PATH = "kctx"
HELM = os.getenv('HELM_CMD', "/usr/local/bin/helm")


class KctxApi:
    def __init__(self, logger):
        self.vault = Vault(logger)
        self.logger = logger

    def execute_command(self, command, kube_env):
        cmd = shlex.split(command)
        res, logs = shell_await(cmd, env=kube_env, with_output=True)
        for l in logs:
            self.logger.info(l)
        return res, logs

    def setup_metrics(self, kube_env):
        """
        Install Metrics API in created cluster

        :param kube_env: env to use for kubernetes communication
        :param tmp_root_path: tmp path to store tmp files
        :return: err code (0 if success), message
        """
        command = "kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.3.6/components.yaml --namespace=kube-system"
        self.execute_command(command, kube_env)

        command = """kubectl patch deployment metrics-server -n kube-system --type=json -p='[{"op":"add", "path":"/spec/template/spec/tolerations", "value":[{"key":"type", "value":"kubsystem", "operator":"Equal", "effect":"NoSchedule"}]}]'"""
        self.execute_command(command, kube_env)

        command = """kubectl patch deployment coredns -n kube-system --type=json -p='[{"op":"add", "path":"/spec/template/spec/tolerations/-", "value":{"key":"type", "value":"kubsystem", "operator":"Equal", "effect":"NoSchedule"}}]'"""
        return self.execute_command(command, kube_env)
