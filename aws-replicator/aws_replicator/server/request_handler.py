import json
import logging
import mimetypes
import os.path
from pathlib import Path
from typing import Dict, List

import yaml
from flask import redirect
from localstack.constants import (
    APPLICATION_OCTET_STREAM,
    INTERNAL_RESOURCE_PATH,
    LOCALHOST_HOSTNAME,
)
from localstack.http import Request, Response, route
from localstack.utils.docker_utils import DOCKER_CLIENT, reserve_available_container_port
from localstack.utils.files import load_file, new_tmp_file, rm_rf
from localstack.utils.json import parse_json_or_yaml
from localstack.utils.strings import to_str
from localstack.utils.threads import start_worker_thread

from aws_replicator import config as repl_config
from aws_replicator.client.auth_proxy import (
    CONTAINER_CONFIG_FILE,
    CONTAINER_NAME_PREFIX,
    start_aws_auth_proxy_in_container,
)
from aws_replicator.config import HANDLER_PATH_PROXIES, HANDLER_PATH_REPLICATE
from aws_replicator.server import ui as web_ui
from aws_replicator.server.aws_request_forwarder import AwsProxyHandler
from aws_replicator.shared.models import AddProxyRequest, ReplicateStateRequest, ResourceReplicator

LOG = logging.getLogger(__name__)

DOMAIN_NAME = f"aws-replicator.{LOCALHOST_HOSTNAME}"
ROUTE_HOST = f"{DOMAIN_NAME}<port:port>"


class RequestHandler:
    @route(HANDLER_PATH_REPLICATE, methods=["POST"])
    def handle_replicate(self, request: Request, **kwargs):
        replicator = _get_replicator()
        payload = _get_json(request)
        if payload:
            req = ReplicateStateRequest(**payload)
            result = replicator.create(req)
        else:
            result = replicator.create_all()
        return result or {}

    @route(HANDLER_PATH_PROXIES, methods=["POST"])
    def add_proxy(self, request: Request, **kwargs):
        payload = _get_json(request)
        req = AddProxyRequest(**payload)
        result = handle_proxies_request(req)
        return result or {}

    @route(f"{HANDLER_PATH_PROXIES}/status", methods=["GET"])
    def get_status(self, request: Request, **kwargs):
        containers = get_proxy_containers()
        status = "enabled" if containers else "disabled"
        config = None
        if containers:
            tmp_file = new_tmp_file()
            container_name = containers[0]["name"]
            try:
                DOCKER_CLIENT.copy_from_container(container_name, tmp_file, CONTAINER_CONFIG_FILE)
                config = load_file(tmp_file)
                config = to_str(yaml.dump(json.loads(config)))
            except Exception as e:
                LOG.debug("Unable to get config from container %s: %s", container_name, e)
            rm_rf(tmp_file)
        return {"status": status, "config": config}

    @route(f"{HANDLER_PATH_PROXIES}/status", methods=["POST"])
    def set_status(self, request: Request, **kwargs):
        payload = _get_json(request) or {}
        if payload.get("status") == "disabled":
            stop_proxy_containers()
        return {}

    @route("/", methods=["GET"], host=ROUTE_HOST)
    def forward_from_root(self, request: Request, **kwargs):
        return redirect(f"{INTERNAL_RESOURCE_PATH}/aws-replicator/index.html")

    @route(f"{INTERNAL_RESOURCE_PATH}/aws-replicator", methods=["GET"])
    def forward_from_extension_root(self, request: Request, **kwargs):
        return redirect(f"{INTERNAL_RESOURCE_PATH}/aws-replicator/index.html")

    @route("/favicon.png", methods=["GET"], host=ROUTE_HOST)
    def serve_favicon(self, request: Request, **kwargs):
        return self.serve_static_file("/favicon.png")

    @route(f"{INTERNAL_RESOURCE_PATH}/aws-replicator/<path:path>", methods=["GET"])
    def get_web_asset(self, request: Request, path: str, **kwargs):
        return self.serve_static_file(path)

    def serve_static_file(self, path: str):
        file_path = os.path.join(os.path.dirname(web_ui.__file__), path.lstrip("/"))
        if not os.path.exists(file_path):
            return Response("File not found", 404)
        mime_type = mimetypes.guess_type(os.path.basename(path))
        mime_type = mime_type[0] if mime_type else APPLICATION_OCTET_STREAM
        return Response(Path(file_path).open(mode="rb"), mimetype=mime_type)


def handle_replicate_request(request: ReplicateStateRequest):
    replicator = _get_replicator()
    return replicator.create(request)


def _get_replicator() -> ResourceReplicator:
    from aws_replicator.server.resource_replicator import ResourceReplicatorFormer2

    # TODO deprecated - fix the implementation of the replicator/copy logic!
    # return ResourceReplicatorInternal()
    return ResourceReplicatorFormer2()


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
            start_aws_auth_proxy_in_container(config, env_vars=env_vars, port=port, quiet=True)

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
