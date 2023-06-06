import logging
import re
from typing import Dict, Optional, Tuple

import boto3
import requests
from botocore.awsrequest import AWSPreparedRequest
from botocore.config import Config
from botocore.model import OperationModel
from localstack.aws.api import HttpRequest
from localstack.aws.protocol.parser import create_parser
from localstack.aws.spec import load_service
from localstack.config import get_edge_url
from localstack.constants import AWS_REGION_US_EAST_1
from localstack.services.generic_proxy import ProxyListener, start_proxy_server
from localstack.utils.bootstrap import setup_logging
from localstack.utils.functions import run_safe
from localstack.utils.net import get_free_tcp_port
from localstack.utils.serving import Server
from localstack.utils.strings import to_str, truncate

from aws_replicator.client.utils import truncate_content
from aws_replicator.config import HANDLER_PATH_PROXIES
from aws_replicator.shared.models import AddProxyRequest, ProxyConfig

LOG = logging.getLogger(__name__)


class AuthProxyAWS(Server):
    def __init__(self, config: ProxyConfig):
        self.config = config
        super().__init__(port=get_free_tcp_port())

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

        # prepare client kwargs - use path addressing style for S3 clients
        kwargs = {}
        # if service_name == "s3":
        #     kwargs = {"config": Config(s3={"addressing_style": "path"})}
        session = boto3.Session()
        client = session.client(service_name, region_name=region_name, **kwargs)

        # fix headers (e.g., "Host") and create client
        self._fix_headers(request, service_name)

        # create request and request dict
        operation_model, aws_request, request_dict = self._parse_aws_request(
            request, service_name, region_name=region_name, client=client
        )

        # adjust request dict and fix certain edge cases in the request
        self._adjust_request_dict(request_dict)

        headers_truncated = {k: truncate(to_str(v)) for k, v in dict(aws_request.headers).items()}
        print(
            "Sending request for service %s to AWS: %s %s - %s - %s",
            service_name,
            method,
            aws_request.url,
            truncate_content(request_dict.get("body"), max_length=500),
            headers_truncated,
        )  # TODO remove
        LOG.debug(
            "Sending request for service %s to AWS: %s %s - %s - %s",
            service_name,
            method,
            aws_request.url,
            truncate_content(request_dict.get("body"), max_length=500),
            headers_truncated,
        )
        try:
            client_endpoint = client._endpoint
            if service_name == "s3":
                _client = session.client(
                    service_name,
                    region_name=region_name,
                    config=Config(s3={"addressing_style": "path"}),
                )
                client_endpoint = _client._endpoint

            # send request to upstream AWS
            print("!!client._endpoint", client_endpoint, client_endpoint.host)  # TODO remove
            result = client_endpoint.make_request(operation_model, request_dict)

            # create response object
            response = requests.Response()
            response.status_code = result[0].status_code
            response._content = result[0].content
            response.headers = dict(result[0].headers)

            print(
                "Received response for service from AWS:",
                service_name,
                response.status_code,
                response.content,
            )  # TODO remove
            LOG.debug(
                "Received response for service %s from AWS: %s - %s",
                service_name,
                response.status_code,
                truncate_content(response.content, max_length=500),
            )
            return response
        except Exception as e:
            LOG.debug("Error when making request to AWS service %s: %s", service_name, e)
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
        print(
            "!!client.meta.config",
            client.meta.config,
            dict(request.headers),
            operation_model,
            operation_model.name,
            operation_model.endpoint,
        )  # TODO CI debugging
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

        # TODO: fix for switch between path/host addressing - seems to be causing issues in CI, to be investigated!
        path_parts = request.path.strip("/").split("/")
        if service_name == "s3" and endpoint_url:
            # path_parts = request_dict.get("url_path", "").strip("/").split("/")
            bucket_subdomain_prefix = f"//{path_parts[0]}.s3."
            if path_parts and bucket_subdomain_prefix in endpoint_url:
                endpoint_url = endpoint_url.replace(bucket_subdomain_prefix, "//s3.")

        # create request dict
        request_dict = client._convert_to_request_dict(
            parsed_request,
            operation_model,
            endpoint_url=endpoint_url,
            context=request_context,
            headers=additional_headers,
        )
        print("!!request_dict", request_dict, endpoint_url)  # TODO CI debugging
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


def start_aws_auth_proxy(config: ProxyConfig) -> AuthProxyAWS:
    setup_logging()
    proxy = AuthProxyAWS(config)
    proxy.start()
    return proxy
