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

    def setup_traefik(self, kube_env):
        """
        Setup traefik plugin in created cluster

        :param kube_env: env to use for kubernetes communication
        :param tmp_root_path: tmp path to store tmp files
        :return: err code (0 if success), message
        """
        command = f'{HELM} repo add traefik https://containous.github.io/traefik-helm-chart'
        self.execute_command(command, kube_env)

        command = f'{HELM} repo update'
        self.execute_command(command, kube_env)

        command = "kubectl create namespace traefik"
        self.execute_command(command, kube_env)

        command = f'{HELM} upgrade --install traefik traefik/traefik ' \
                  f'--set service.type=NodePort ' \
                  f'--set ports.web.nodePort=30003 ' \
                  f'--set ports.discovery.port=8001 ' \
                  f'--set ports.discovery.expose=true ' \
                  f'--set ports.discovery.exposedPort=5801 ' \
                  f'--set ports.discovery.nodePort=30004 ' \
                  f'--set ports.external.port=8002 ' \
                  f'--set ports.external.expose=true ' \
                  f'--set ports.external.exposedPort=20000 ' \
                  f'--set ports.external.nodePort=30005 ' \
                  f'--set tolerations[0].key=type ' \
                  f'--set tolerations[0].value=kubsystem ' \
                  f'--set tolerations[0].operator=Equal ' \
                  f'--set tolerations[0].effect=NoSchedule ' \
                  f'--namespace traefik'
        return self.execute_command(command, kube_env)

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
