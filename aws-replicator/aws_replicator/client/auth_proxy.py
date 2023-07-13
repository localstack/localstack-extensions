import json
import logging
import os
import re
import subprocess
import sys
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import boto3
import requests
from botocore.awsrequest import AWSPreparedRequest
from botocore.model import OperationModel
from localstack import config as localstack_config
from localstack.aws.api import HttpRequest
from localstack.aws.protocol.parser import create_parser
from localstack.aws.spec import load_service
from localstack.config import get_edge_url
from localstack.constants import AWS_REGION_US_EAST_1, DOCKER_IMAGE_NAME_PRO
from localstack.services.generic_proxy import ProxyListener, start_proxy_server
from localstack.utils.bootstrap import setup_logging
from localstack.utils.collections import select_attributes
from localstack.utils.container_utils.container_client import PortMappings
from localstack.utils.docker_utils import DOCKER_CLIENT, reserve_available_container_port
from localstack.utils.files import new_tmp_file, save_file
from localstack.utils.functions import run_safe
from localstack.utils.net import get_free_tcp_port
from localstack.utils.serving import Server
from localstack.utils.strings import short_uid, to_str, truncate
from localstack_ext.bootstrap.licensing import ENV_LOCALSTACK_API_KEY

from aws_replicator.client.utils import truncate_content
from aws_replicator.config import HANDLER_PATH_PROXIES
from aws_replicator.shared.models import AddProxyRequest, ProxyConfig

LOG = logging.getLogger(__name__)

# TODO make configurable
CLI_PIP_PACKAGE = "git+https://github.com/localstack/localstack-extensions/@main#egg=localstack-extension-aws-replicator&subdirectory=aws-replicator"


class AuthProxyAWS(Server):
    def __init__(self, config: ProxyConfig, port: int = None):
        self.config = config
        port = port or get_free_tcp_port()
        super().__init__(port=port)

    def do_run(self):
        class Handler(ProxyListener):
            def forward_request(_self, method, path, data, headers):
                return self.proxy_request(method, path, data, headers)

        self.register_in_instance()
        # TODO: change to using Gateway!
        proxy = start_proxy_server(self.port, update_listener=Handler())
        proxy.join()

    def proxy_request(self, method, path, data, headers):
        parsed = self._extract_region_and_service(headers)
        if not parsed:
            return 400
        region_name, service_name = parsed

        LOG.debug(
            "Proxying request to %s (%s): %s %s",
            service_name,
            region_name,
            method,
            path,
        )

        path, _, query_string = path.partition("?")
        request = HttpRequest(
            body=data,
            method=method,
            headers=headers,
            path=path,
            query_string=query_string,
        )
        session = boto3.Session()
        client = session.client(service_name, region_name=region_name)

        # fix headers (e.g., "Host") and create client
        self._fix_headers(request, service_name)

        # create request and request dict
        operation_model, aws_request, request_dict = self._parse_aws_request(
            request, service_name, region_name=region_name, client=client
        )

        # adjust request dict and fix certain edge cases in the request
        self._adjust_request_dict(request_dict)

        headers_truncated = {k: truncate(to_str(v)) for k, v in dict(aws_request.headers).items()}
        LOG.debug(
            "Sending request for service %s to AWS: %s %s - %s - %s",
            service_name,
            method,
            aws_request.url,
            truncate_content(request_dict.get("body"), max_length=500),
            headers_truncated,
        )
        try:
            # send request to upstream AWS
            result = client._endpoint.make_request(operation_model, request_dict)

            # create response object
            response = requests.Response()
            response.status_code = result[0].status_code
            response._content = result[0].content
            response.headers = dict(result[0].headers)

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
            return 400

    def register_in_instance(self):
        port = getattr(self, "port", None)
        if not port:
            raise Exception("Proxy currently not running")
        url = f"{get_edge_url()}{HANDLER_PATH_PROXIES}"
        data = AddProxyRequest(port=port, config=self.config)
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
        self, request: HttpRequest, service_name: str, region_name: str, client
    ) -> Tuple[OperationModel, AWSPreparedRequest, Dict]:
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
        endpoint_url, additional_headers = client._resolve_endpoint_ruleset(
            operation_model, parsed_request, request_context
        )

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

    def _adjust_request_dict(self, request_dict: Dict):
        """Apply minor fixes to the request dict, which seem to be required in the current setup."""

        body_str = run_safe(lambda: to_str(request_dict["body"])) or ""

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

    def _fix_headers(self, request: HttpRequest, service_name: str):
        if service_name == "s3":
            # fix the Host header, to avoid bucket addressing issues
            host = request.headers.get("Host") or ""
            regex = r"^(https?://)?([0-9.]+|localhost)(:[0-9]+)?"
            if re.match(regex, host):
                request.headers["Host"] = re.sub(regex, r"\1s3.localhost.localstack.cloud", host)
        request.headers.pop("Content-Length", None)
        request.headers.pop("x-localstack-request-url", None)
        request.headers.pop("X-Forwarded-For", None)
        request.headers.pop("Remote-Addr", None)

    def _extract_region_and_service(self, headers) -> Optional[Tuple[str, str]]:
        auth_header = headers.pop("Authorization", "")
        parts = auth_header.split("Credential=", maxsplit=1)
        if len(parts) < 2:
            return
        parts = parts[1].split("/")
        if len(parts) < 5:
            return
        return parts[2], parts[3]


def start_aws_auth_proxy(config: ProxyConfig, port: int = None) -> AuthProxyAWS:
    setup_logging()
    proxy = AuthProxyAWS(config, port=port)
    proxy.start()
    return proxy


def start_aws_auth_proxy_in_container(config: ProxyConfig):
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
    port = reserve_available_container_port()
    ports = PortMappings()
    ports.add(port, port)

    # create container
    container_name = f"ls-aws-proxy-{short_uid()}"
    image_name = DOCKER_IMAGE_NAME_PRO
    DOCKER_CLIENT.create_container(
        image_name,
        name=container_name,
        entrypoint="",
        command=["bash", "-c", "while true; do sleep 1; done"],
        ports=ports,
    )

    # start container in detached mode
    DOCKER_CLIENT.start_container(container_name)

    # install extension CLI package
    venv_activate = ". .venv/bin/activate"
    command = [
        "bash",
        "-c",
        f"{venv_activate}; pip install --upgrade --no-deps '{CLI_PIP_PACKAGE}'",
    ]
    DOCKER_CLIENT.exec_in_container(container_name, command=command)

    # create config file in container
    config_file_host = new_tmp_file()
    save_file(config_file_host, json.dumps(config))
    config_file_cnt = "/tmp/ls.aws.proxy.yml"
    DOCKER_CLIENT.copy_into_container(
        container_name, config_file_host, container_path=config_file_cnt
    )

    # prepare environment variables
    env_var_names = [
        "DEBUG",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
        ENV_LOCALSTACK_API_KEY,
    ]
    env_vars = select_attributes(dict(os.environ), env_var_names)
    env_vars["LOCALSTACK_HOSTNAME"] = "host.docker.internal"

    try:
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
            f"{venv_activate}; localstack aws proxy -c {config_file_cnt} -p {port}",
        ]
        print("Proxy container is ready.")
        subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Error:", e)
    finally:
        DOCKER_CLIENT.remove_container(container_name, force=True)
