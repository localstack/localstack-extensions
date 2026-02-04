# Note/disclosure: This file has been partially modified by an AI agent.
import json
import logging
import os.path
from typing import Dict, List

import yaml
from localstack.constants import (
    LOCALHOST_HOSTNAME,
)
from localstack.http import Request, Response, route
from localstack.utils.docker_utils import (
    DOCKER_CLIENT,
    reserve_available_container_port,
)
from localstack.utils.files import load_file, new_tmp_file, rm_rf
from localstack.utils.json import parse_json_or_yaml
from localstack.utils.strings import to_str
from localstack.utils.threads import start_worker_thread

from aws_proxy import config as repl_config
from aws_proxy.client.auth_proxy import (
    CONTAINER_CONFIG_FILE,
    CONTAINER_NAME_PREFIX,
    start_aws_auth_proxy_in_container,
)
from aws_proxy.config import HANDLER_PATH_PROXIES
from aws_proxy.server.aws_request_forwarder import AwsProxyHandler
from aws_proxy.shared.models import AddProxyRequest

from . import static

LOG = logging.getLogger(__name__)

DOMAIN_NAME = f"aws-proxy.{LOCALHOST_HOSTNAME}"
ROUTE_HOST = f"{DOMAIN_NAME}<port:port>"


class RequestHandler:
    @route(HANDLER_PATH_PROXIES, methods=["POST"])
    def add_proxy(self, request: Request, **kwargs):
        payload = _get_json(request)
        req = AddProxyRequest(**payload)
        result = handle_proxies_request(req)
        return result or {}

    @route(f"{HANDLER_PATH_PROXIES}/<int:port>", methods=["DELETE"])
    def delete_proxy(self, request: Request, port: int, **kwargs):
        removed = AwsProxyHandler.PROXY_INSTANCES.pop(port, None)
        return {"removed": removed is not None}

    @route(f"{HANDLER_PATH_PROXIES}/status", methods=["GET"])
    def get_status(self, request: Request, **kwargs):
        containers = get_proxy_containers()
        status = "enabled" if containers else "disabled"
        config = None
        if containers:
            tmp_file = new_tmp_file()
            container_name = containers[0]["name"]
            try:
                DOCKER_CLIENT.copy_from_container(
                    container_name, tmp_file, CONTAINER_CONFIG_FILE
                )
                config = load_file(tmp_file)
                config = to_str(yaml.dump(json.loads(config)))
            except Exception as e:
                LOG.debug(
                    "Unable to get config from container %s: %s", container_name, e
                )
            rm_rf(tmp_file)
        return {"status": status, "config": config}

    @route(f"{HANDLER_PATH_PROXIES}/status", methods=["POST"])
    def set_status(self, request: Request, **kwargs):
        payload = _get_json(request) or {}
        if payload.get("status") == "disabled":
            stop_proxy_containers()
        return {}


class WebApp:
    @route("/")
    def index(self, request: Request, *args, **kwargs):
        return Response.for_resource(static, "index.html")

    @route("/<path:path>")
    def index2(self, request: Request, path: str, **kwargs):
        try:
            return Response.for_resource(static, path)
        except Exception:
            LOG.debug(f"File {path} not found, serving index.html")
            return Response.for_resource(static, "index.html")


def handle_proxies_request(request: AddProxyRequest):
    port = request.get("port")
    if not port:
        # this request is coming from the Web UI (not from the CLI) - choose a new port at random
        port = request["port"] = reserve_available_container_port()
        # simple approach for now: managing a single proxy container (might become multiple in future)
        stop_proxy_containers()

        env_vars = dict(os.environ)
        env_vars.update(request.get("env_vars") or {})
        config = request["config"]
        if isinstance(config, str):
            request["config"] = config = parse_json_or_yaml(config) or {}

        def _start(*_):
            start_aws_auth_proxy_in_container(
                config, env_vars=env_vars, port=port, quiet=True
            )

        start_worker_thread(_start)

    AwsProxyHandler.PROXY_INSTANCES[port] = request
    return {}


def get_proxy_containers() -> List[Dict]:
    return DOCKER_CLIENT.list_containers(filter=f"name={CONTAINER_NAME_PREFIX}*")


def stop_proxy_containers():
    for container in get_proxy_containers():
        try:
            DOCKER_CLIENT.stop_container(container["name"])
            if repl_config.CLEANUP_PROXY_CONTAINERS:
                DOCKER_CLIENT.remove_container(container["name"], force=True)
        except Exception as e:
            LOG.debug("Unable to remove container %s: %s", container["name"], e)


def _get_json(request: Request) -> dict:
    try:
        return request.json
    except Exception:
        return json.loads(to_str(request.data))
