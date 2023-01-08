import json
import logging
import re
from typing import Dict, Optional

import requests
from localstack import config
from localstack.aws.api import RequestContext
from localstack.aws.chain import Handler, HandlerChain
from localstack.constants import APPLICATION_JSON, LOCALHOST, LOCALHOST_HOSTNAME
from localstack.http import Response
from localstack.utils.aws.aws_stack import get_valid_regions, mock_aws_request_headers
from requests.structures import CaseInsensitiveDict

from aws_replicator.shared.models import ProxyInstance

LOG = logging.getLogger(__name__)


class AwsProxyHandler(Handler):

    # maps port numbers to proxy instances
    PROXY_INSTANCES: Dict[int, ProxyInstance] = {}

    def __call__(self, chain: HandlerChain, context: RequestContext, response: Response):
        proxy = self.select_proxy(context)
        if not proxy:
            return
        if not self.should_forward(context, proxy):
            return

        # forward request to proxy
        response = self.forward_request(context, proxy)

        if response is None:
            return
        if response.status_code == 404:
            # TODO: make this fallback configurable?
            return

        # set response details, then stop handler chain to return response
        chain.response.data = response.content
        chain.response.status_code = response.status_code
        chain.response.headers.update(dict(response.headers))
        chain.stop()

    def select_proxy(self, context: RequestContext) -> Optional[ProxyInstance]:
        """select a proxy responsible to forward a request to real AWS"""
        for port, proxy in self.PROXY_INSTANCES.items():
            if context.service.service_name in proxy["services"]:
                return proxy

    def forward_request(self, context: RequestContext, proxy: ProxyInstance):
        port = proxy["port"]
        request = context.request
        target_host = config.DOCKER_HOST_FROM_CONTAINER if config.is_in_docker else LOCALHOST
        url = f"http://{target_host}:{port}{request.path}"

        # inject Auth header, to ensure we're passing the right region to the proxy (e.g., for Cognito InitiateAuth)
        self._extract_region_from_domain(context)
        headers = CaseInsensitiveDict(dict(request.headers))

        result = None
        try:
            headers.pop("Host", None)
            headers.pop("Content-Length", None)
            ctype = headers.get("Content-Type")
            data = b""
            if ctype == APPLICATION_JSON:
                data = json.dumps(request.json)
            elif request.form:
                data = request.form
            elif request.data:
                data = request.data
            LOG.debug("Forward request: %s %s - %s - %s", request.method, url, dict(headers), data)
            result = requests.request(
                method=request.method, url=url, data=data, headers=dict(headers)
            )
            LOG.debug(
                "Returned response: %s %s - %s",
                result.status_code,
                dict(result.headers),
                result.content,
            )
        except requests.exceptions.ConnectionError:
            # remove unreachable proxy
            LOG.info("Removing unreachable AWS forward proxy due to connection issue: %s", url)
            self.PROXY_INSTANCES.pop(port, None)
        return result

    def should_forward(self, context: RequestContext, proxy: ProxyInstance) -> bool:
        # TODO: make configurable whether proxies should be read-only or write-enabled!
        return self._is_read_request(context)

    def _is_read_request(self, context: RequestContext) -> bool:
        operation_name = context.service_operation.operation
        if operation_name.lower().startswith(("describe", "get", "list", "query")):
            return True
        # service-specific rules
        if context.service.service_name == "cognito-idp" and operation_name == "InitiateAuth":
            return True
        return False

    def _extract_region_from_domain(self, context: RequestContext):
        """
        If the request domain name contains a valid region name (e.g., "us-east-2.cognito.localhost.localstack.cloud"),
        extract the region and inject an Authorization header with this region into the request.
        """
        headers = CaseInsensitiveDict(dict(context.request.headers))
        host_header = headers.get("Host") or ""
        if LOCALHOST_HOSTNAME not in host_header:
            return
        parts = re.split("[.:/]+", host_header)
        valid_regions = get_valid_regions()
        for part in parts:
            if part in valid_regions:
                context.request.headers["Authorization"] = mock_aws_request_headers(
                    context.service.service_name, region_name=part
                )
                return
