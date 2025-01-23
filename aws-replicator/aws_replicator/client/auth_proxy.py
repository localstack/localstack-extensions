import json
import logging
import os
import re
import subprocess
import sys
from functools import cache
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import boto3
import requests
from botocore.awsrequest import AWSPreparedRequest
from botocore.model import OperationModel
from localstack import config as localstack_config
from localstack.aws.spec import load_service
from localstack.config import external_service_url
from localstack.constants import AWS_REGION_US_EAST_1, DOCKER_IMAGE_NAME_PRO, LOCALHOST_HOSTNAME
from localstack.http import Request
from localstack.utils.aws.aws_responses import requests_response
from localstack.utils.bootstrap import setup_logging
from localstack.utils.collections import select_attributes
from localstack.utils.container_utils.container_client import PortMappings
from localstack.utils.docker_utils import DOCKER_CLIENT, reserve_available_container_port
from localstack.utils.files import new_tmp_file, save_file
from localstack.utils.functions import run_safe
from localstack.utils.net import get_docker_host_from_container, get_free_tcp_port
from localstack.utils.serving import Server
from localstack.utils.strings import short_uid, to_bytes, to_str, truncate
from requests import Response

from aws_replicator import config as repl_config
from aws_replicator.client.utils import truncate_content
from aws_replicator.config import HANDLER_PATH_PROXIES
from aws_replicator.shared.constants import HEADER_HOST_ORIGINAL
from aws_replicator.shared.models import AddProxyRequest, ProxyConfig

from .http2_server import run_server

try:
    from localstack.pro.core.bootstrap.licensingv2 import (
        ENV_LOCALSTACK_API_KEY,
        ENV_LOCALSTACK_AUTH_TOKEN,
    )
except ImportError:
    # TODO remove once we don't need compatibility with <3.6 anymore
    from localstack_ext.bootstrap.licensingv2 import (
        ENV_LOCALSTACK_API_KEY,
        ENV_LOCALSTACK_AUTH_TOKEN,
    )

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)
if localstack_config.DEBUG:
    LOG.setLevel(logging.DEBUG)

# TODO make configurable
CLI_PIP_PACKAGE = "localstack-extension-aws-replicator"
# note: enable the line below temporarily for testing:
# CLI_PIP_PACKAGE = "git+https://github.com/localstack/localstack-extensions/@branch#egg=localstack-extension-aws-replicator&subdirectory=aws-replicator"

CONTAINER_NAME_PREFIX = "ls-aws-proxy-"
CONTAINER_CONFIG_FILE = "/tmp/ls.aws.proxy.yml"
CONTAINER_LOG_FILE = "/tmp/ls-aws-proxy.log"

# default bind host if `bind_host` is not specified for the proxy
DEFAULT_BIND_HOST = "127.0.0.1"


class AuthProxyAWS(Server):
    def __init__(self, config: ProxyConfig, port: int = None):
        self.config = config
        port = port or get_free_tcp_port()
        super().__init__(port=port)

    def do_run(self):
        self.register_in_instance()
        bind_host = self.config.get("bind_host") or DEFAULT_BIND_HOST
        proxy = run_server(port=self.port, bind_addresses=[bind_host], handler=self.proxy_request)
        proxy.join()

    def proxy_request(self, request: Request, data: bytes) -> Response:
        parsed = self._extract_region_and_service(request.headers)
        if not parsed:
            return requests_response("", status_code=400)
        region_name, service_name = parsed
        query_string = to_str(request.query_string or "")

        LOG.debug(
            "Proxying request to %s (%s): %s %s %s",
            service_name,
            region_name,
            request.method,
            request.path,
            query_string,
        )

        request = Request(
            body=data,
            method=request.method,
            headers=request.headers,
            path=request.path,
            query_string=query_string,
        )
        session = boto3.Session()
        client = session.client(service_name, region_name=region_name)

        # fix headers (e.g., "Host") and create client
        self._fix_headers(request, service_name)
        self._fix_host_and_path(request, service_name)

        # create request and request dict
        operation_model, aws_request, request_dict = self._parse_aws_request(
            request, service_name, region_name=region_name, client=client
        )

        # adjust request dict and fix certain edge cases in the request
        self._adjust_request_dict(service_name, request_dict)

        headers_truncated = {k: truncate(to_str(v)) for k, v in dict(aws_request.headers).items()}
        LOG.debug(
            "Sending request for service %s to AWS: %s %s - %s - %s",
            service_name,
            request.method,
            aws_request.url,
            truncate_content(request_dict.get("body"), max_length=500),
            headers_truncated,
        )
        try:
            # send request to upstream AWS
            result = client._endpoint.make_request(operation_model, request_dict)

            # create response object - TODO: to be replaced with localstack.http.Response over time
            response = requests_response(
                result[0].content,
                status_code=result[0].status_code,
                headers=dict(result[0].headers),
            )

            LOG.debug(
                "Received response for service %s from AWS: %s - %s",
                service_name,
                response.status_code,
                truncate_content(response.content, max_length=500),
            )
            return response
        except Exception as e:
            if LOG.isEnabledFor(logging.DEBUG):
                LOG.exception("Error when making request to AWS service %s: %s", service_name, e)
            return requests_response("", status_code=400)

    def register_in_instance(self):
        port = getattr(self, "port", None)
        if not port:
            raise Exception("Proxy currently not running")
        url = f"{external_service_url()}{HANDLER_PATH_PROXIES}"
        data = AddProxyRequest(port=port, config=self.config)
        LOG.debug("Registering new proxy in main container via: %s", url)
        try:
            response = requests.post(url, json=data)
            assert response.ok
            return response
        except Exception:
            LOG.warning(
                "Unable to register auth proxy - is LocalStack running with the extension enabled?"
            )
            raise

    def _parse_aws_request(
        self, request: Request, service_name: str, region_name: str, client
    ) -> Tuple[OperationModel, AWSPreparedRequest, Dict]:
        from localstack.aws.protocol.parser import create_parser

        parser = create_parser(load_service(service_name))
        operation_model, parsed_request = parser.parse(request)
        request_context = {
            "client_region": region_name,
            "has_streaming_input": operation_model.has_streaming_input,
            "auth_type": operation_model.auth_type,
            "client_config": client.meta.config,
        }
        parsed_request = {} if parsed_request is None else parsed_request
        parsed_request = {k: v for k, v in parsed_request.items() if v is not None}

        # get endpoint info
        endpoint_info = client._resolve_endpoint_ruleset(
            operation_model, parsed_request, request_context
        )
        # switch for https://github.com/boto/botocore/commit/826b78c54dd87b9da368e9ab6017d8c4823b28c1
        if len(endpoint_info) == 3:
            endpoint_url, additional_headers, properties = endpoint_info
            if properties:
                request_context["endpoint_properties"] = properties
        else:
            endpoint_url, additional_headers = endpoint_info

        # create request dict
        request_dict = client._convert_to_request_dict(
            parsed_request,
            operation_model,
            endpoint_url=endpoint_url,
            context=request_context,
            headers=additional_headers,
        )

        # TODO: fix for switch between path/host addressing
        # Note: the behavior seems to be different across botocore versions. Seems to be working
        # with 1.29.97 (fix below not required) whereas newer versions like 1.29.151 require the fix.
        if service_name == "s3":
            request_url = request_dict["url"]
            url_parsed = list(urlparse(request_url))
            path_parts = url_parsed[2].strip("/").split("/")
            bucket_subdomain_prefix = f"://{path_parts[0]}.s3."
            if bucket_subdomain_prefix in request_url:
                prefix = f"/{path_parts[0]}"
                url_parsed[2] = url_parsed[2].removeprefix(prefix)
                request_dict["url_path"] = request_dict["url_path"].removeprefix(prefix)
                # replace empty path with "/" (seems required for signature calculation)
                request_dict["url_path"] = request_dict["url_path"] or "/"
                url_parsed[2] = url_parsed[2] or "/"
                # re-construct final URL
                request_dict["url"] = urlunparse(url_parsed)

        aws_request = client._endpoint.create_request(request_dict, operation_model)

        return operation_model, aws_request, request_dict

    def _adjust_request_dict(self, service_name: str, request_dict: Dict):
        """Apply minor fixes to the request dict, which seem to be required in the current setup."""

        req_body = request_dict.get("body")
        body_str = run_safe(lambda: to_str(req_body)) or ""

        # TODO: this custom fix should not be required - investigate and remove!
        if "<CreateBucketConfiguration" in body_str and "LocationConstraint" not in body_str:
            region = request_dict["context"]["client_region"]
            if region == AWS_REGION_US_EAST_1:
                request_dict["body"] = ""
            else:
                request_dict["body"] = (
                    '<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                    f"<LocationConstraint>{region}</LocationConstraint></CreateBucketConfiguration>"
                )

        if service_name == "sqs" and isinstance(req_body, dict):
            account_id = self._query_account_id_from_aws()
            if "QueueUrl" in req_body:
                queue_name = req_body["QueueUrl"].split("/")[-1]
                req_body["QueueUrl"] = f"https://queue.amazonaws.com/{account_id}/{queue_name}"
            if "QueueOwnerAWSAccountId" in req_body:
                req_body["QueueOwnerAWSAccountId"] = account_id
        if service_name == "sqs" and request_dict.get("url"):
            req_json = run_safe(lambda: json.loads(body_str)) or {}
            account_id = self._query_account_id_from_aws()
            queue_name = req_json.get("QueueName")
            if account_id and queue_name:
                request_dict["url"] = f"https://queue.amazonaws.com/{account_id}/{queue_name}"
                req_json["QueueOwnerAWSAccountId"] = account_id
                request_dict["body"] = to_bytes(json.dumps(req_json))

    def _fix_headers(self, request: Request, service_name: str):
        if service_name == "s3":
            # fix the Host header, to avoid bucket addressing issues
            host = request.headers.get("Host") or ""
            regex = r"^(https?://)?([0-9.]+|localhost)(:[0-9]+)?"
            if re.match(regex, host):
                request.headers["Host"] = re.sub(regex, rf"\1s3.{LOCALHOST_HOSTNAME}", host)
        request.headers.pop("Content-Length", None)
        request.headers.pop("x-localstack-request-url", None)
        request.headers.pop("X-Forwarded-For", None)
        request.headers.pop("X-Localstack-Tgt-Api", None)
        request.headers.pop("X-Moto-Account-Id", None)
        request.headers.pop("Remote-Addr", None)

    def _fix_host_and_path(self, request: Request, service_name: str):
        if service_name == "s3":
            # fix the path and prepend the bucket name, to avoid bucket addressing issues
            regex_base_domain = rf"((amazonaws\.com)|({LOCALHOST_HOSTNAME}))"
            host = request.headers.pop(HEADER_HOST_ORIGINAL, None)
            host = host or request.headers.get("Host") or ""
            match = re.match(rf"(.+)\.s3\..*{regex_base_domain}", host)
            if match:
                # prepend the bucket name (extracted from the host) to the path of the request (path-based addressing)
                request.path = f"/{match.group(1)}{request.path}"

    def _extract_region_and_service(self, headers) -> Optional[Tuple[str, str]]:
        auth_header = headers.pop("Authorization", "")
        parts = auth_header.split("Credential=", maxsplit=1)
        if len(parts) < 2:
            return
        parts = parts[1].split("/")
        if len(parts) < 5:
            return
        return parts[2], parts[3]

    @cache
    def _query_account_id_from_aws(self) -> str:
        session = boto3.Session()
        sts_client = session.client("sts")
        result = sts_client.get_caller_identity()
        return result["Account"]


def start_aws_auth_proxy(config: ProxyConfig, port: int = None) -> AuthProxyAWS:
    setup_logging()
    proxy = AuthProxyAWS(config, port=port)
    proxy.start()
    return proxy


def start_aws_auth_proxy_in_container(
    config: ProxyConfig, env_vars: dict = None, port: int = None, quiet: bool = False
):
    """
    Run the auth proxy in a separate local container. This can help in cases where users
    are running into version/dependency issues on their host machines.
    """
    # TODO: Currently running a container and installing the extension on the fly - we
    #  should consider building pre-baked images for the extension in the future. Also,
    #  the new packaged CLI binary can help us gain more stability over time...

    logging.getLogger("localstack.utils.container_utils.docker_cmd_client").setLevel(logging.INFO)
    logging.getLogger("localstack.utils.docker_utils").setLevel(logging.INFO)
    logging.getLogger("localstack.utils.run").setLevel(logging.INFO)

    print("Proxy container is starting up...")

    # determine port mapping
    localstack_config.PORTS_CHECK_DOCKER_IMAGE = DOCKER_IMAGE_NAME_PRO
    port = port or reserve_available_container_port()
    ports = PortMappings()
    ports.add(port, port)

    # create container
    container_name = f"{CONTAINER_NAME_PREFIX}{short_uid()}"
    image_name = DOCKER_IMAGE_NAME_PRO
    # add host mapping for localstack.cloud to localhost to prevent the health check from failing
    additional_flags = (
        repl_config.PROXY_DOCKER_FLAGS + " --add-host=localhost.localstack.cloud:host-gateway"
    )
    DOCKER_CLIENT.create_container(
        image_name,
        name=container_name,
        entrypoint="",
        command=["bash", "-c", f"touch {CONTAINER_LOG_FILE}; tail -f {CONTAINER_LOG_FILE}"],
        ports=ports,
        additional_flags=additional_flags,
    )

    # start container in detached mode
    DOCKER_CLIENT.start_container(container_name, attach=False)

    # install extension CLI package
    venv_activate = ". .venv/bin/activate"
    command = [
        "bash",
        "-c",
        # TODO: manually installing quart/h11/hypercorn as a dirty quick fix for now. To be fixed!
        f"{venv_activate}; pip install h11 hypercorn quart; pip install --upgrade --no-deps '{CLI_PIP_PACKAGE}'",
    ]
    DOCKER_CLIENT.exec_in_container(container_name, command=command)

    # create config file in container
    config_file_host = new_tmp_file()
    save_file(config_file_host, json.dumps(config))
    DOCKER_CLIENT.copy_into_container(
        container_name, config_file_host, container_path=CONTAINER_CONFIG_FILE
    )

    # prepare environment variables
    env_var_names = [
        "DEBUG",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
        ENV_LOCALSTACK_API_KEY,
        ENV_LOCALSTACK_AUTH_TOKEN,
    ]
    env_vars = env_vars or os.environ
    env_vars = select_attributes(dict(env_vars), env_var_names)

    # Determine target hostname - we make the host configurable via PROXY_LOCALSTACK_HOST,
    #  and if not configured then use get_docker_host_from_container() as a fallback.
    target_host = repl_config.PROXY_LOCALSTACK_HOST
    if not repl_config.PROXY_LOCALSTACK_HOST:
        target_host = get_docker_host_from_container()
    env_vars["LOCALSTACK_HOST"] = target_host

    # Use the Docker SDK command either if quiet mode is enabled, or if we're executing
    # in Docker itself (e.g., within the LocalStack main container, as part of an init script)
    use_docker_sdk_command = quiet or localstack_config.is_in_docker

    try:
        print("Proxy container is ready.")
        command = f"{venv_activate}; localstack aws proxy -c {CONTAINER_CONFIG_FILE} -p {port} --host 0.0.0.0 > {CONTAINER_LOG_FILE} 2>&1"
        if use_docker_sdk_command:
            DOCKER_CLIENT.exec_in_container(
                container_name, command=["bash", "-c", command], env_vars=env_vars, interactive=True
            )
        else:
            env_vars_list = []
            for key, value in env_vars.items():
                env_vars_list += ["-e", f"{key}={value}"]
            # note: using docker command directly, as our Docker client doesn't fully support log piping yet
            command = [
                "docker",
                "exec",
                "-it",
                *env_vars_list,
                container_name,
                "bash",
                "-c",
                command,
            ]
            subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        LOG.info("Error: %s", e)
        if isinstance(e, subprocess.CalledProcessError):
            LOG.info("Error in called process - output: %s\n%s", e.stdout, e.stderr)
    finally:
        try:
            if repl_config.CLEANUP_PROXY_CONTAINERS:
                DOCKER_CLIENT.remove_container(container_name, force=True)
        except Exception as e:
            if "already in progress" not in str(e):
                raise
