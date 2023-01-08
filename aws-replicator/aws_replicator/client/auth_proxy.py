import logging
import re
from typing import List, Optional, Tuple

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from localstack.aws.api import HttpRequest
from localstack.aws.protocol.parser import create_parser
from localstack.aws.spec import load_service
from localstack.config import get_edge_url
from localstack.constants import INTERNAL_RESOURCE_PATH
from localstack.services.generic_proxy import ProxyListener, start_proxy_server
from localstack.utils.bootstrap import setup_logging
from localstack.utils.net import get_free_tcp_port
from localstack.utils.strings import to_str, truncate

from aws_replicator.client.utils import truncate_content
from aws_replicator.config import HANDLER_PATH_PROXIES
from aws_replicator.shared.models import AddProxyRequest

LOG = logging.getLogger(__name__)


class AuthProxyAWS:
    def __init__(self, services: List[str]):
        self.services = services

    def start(self):
        class Handler(ProxyListener):
            def forward_request(_self, method, path, data, headers):
                return self.proxy_request(method, path, data, headers)

        self.port = get_free_tcp_port()
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

        # create signed request
        aws_request, signing_region = self._parse_aws_request(
            request, service_name, region_name, client
        )
        headers = {k: to_str(v) for k, v in aws_request.headers.items()}
        # need to convert from AWSPreparedRequest to AWSRequest, as this is what add_auth(..) expects
        aws_request = AWSRequest(
            method=method, headers=headers, url=aws_request.url, data=aws_request.body
        )
        url = aws_request.url
        credentials = session.get_credentials()
        signer = SigV4Auth(credentials, service_name, region_name=signing_region)
        signer.add_auth(aws_request)

        headers_truncated = {k: truncate(v) for k, v in dict(aws_request.headers).items()}
        LOG.debug(
            "Sending request for service %s to AWS: %s %s - %s - %s",
            service_name,
            method,
            url,
            truncate_content(data, max_length=500),
            headers_truncated,
        )
        try:
            # send request to upstream AWS
            response = requests.request(
                method=method, url=url, data=aws_request.data, headers=aws_request.headers
            )
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
        url = f"{get_edge_url()}{INTERNAL_RESOURCE_PATH}{HANDLER_PATH_PROXIES}"
        data = AddProxyRequest(port=port, services=self.services)
        try:
            response = requests.post(url, json=data)
            assert response.ok
            return response
        except Exception:
            LOG.warning(
                "Unable to register auth proxy - is LocalStack running with the extension enabled?"
            )
            raise

    def _parse_aws_request(self, request: HttpRequest, service_name: str, region_name: str, client):
        parser = create_parser(load_service(service_name))
        operation_model, parsed_request = parser.parse(request)
        request_context = {
            "client_region": region_name,
            "has_streaming_input": operation_model.has_streaming_input,
            "auth_type": operation_model.auth_type,
        }
        parsed_request = {} if parsed_request is None else parsed_request
        parsed_request = {k: v for k, v in parsed_request.items() if v is not None}
        endpoint_url, additional_headers = client._resolve_endpoint_ruleset(
            operation_model, parsed_request, request_context
        )
        request_dict = client._convert_to_request_dict(
            parsed_request,
            operation_model,
            endpoint_url,
            context=request_context,
            headers=additional_headers,
        )
        aws_request = client._endpoint.create_request(request_dict, operation_model)

        if request_dict.get("body"):
            # overwrite request data, to avoid divergence in Content-Length (e.g., in case of JSON
            # formatting with/without whitespaces) and hence invalid request signatures
            aws_request.body = request_dict["body"]
        signing_region = (
            request_dict.get("context", {}).get("signing", {}).get("region") or region_name
        )

        return aws_request, signing_region

    def _fix_headers(self, request, service_name):
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


def start_aws_auth_proxy(services: List[str]):
    setup_logging()
    proxy = AuthProxyAWS(services)
    proxy.start()
