import json
import logging
import re
from typing import Dict, Optional

import requests
from localstack.aws.api import RequestContext
from localstack.aws.chain import Handler, HandlerChain
from localstack.constants import APPLICATION_JSON, LOCALHOST, LOCALHOST_HOSTNAME
from localstack.http import Response
from localstack.utils.aws import arns
from localstack.utils.aws.arns import secretsmanager_secret_arn, sqs_queue_arn
from localstack.utils.aws.aws_stack import get_valid_regions
from localstack.utils.aws.request_context import mock_aws_request_headers
from localstack.utils.collections import ensure_list
from localstack.utils.net import get_addressable_container_host
from localstack.utils.strings import to_str, truncate
from requests.structures import CaseInsensitiveDict

try:
    from localstack.testing.config import TEST_AWS_ACCESS_KEY_ID
except ImportError:
    from localstack.constants import TEST_AWS_ACCESS_KEY_ID

from aws_replicator.shared.constants import HEADER_HOST_ORIGINAL
from aws_replicator.shared.models import ProxyInstance, ProxyServiceConfig

LOG = logging.getLogger(__name__)


class AwsProxyHandler(Handler):
    # maps port numbers to proxy instances
    PROXY_INSTANCES: Dict[int, ProxyInstance] = {}

    def __call__(self, chain: HandlerChain, context: RequestContext, response: Response):
        proxy = self.select_proxy(context)
        if not proxy:
            return

        # forward request to proxy
        response = self.forward_request(context, proxy)

        if response is None:
            return

        # set response details, then stop handler chain to return response
        chain.response.data = response.raw_content
        chain.response.status_code = response.status_code
        chain.response.headers.update(dict(response.headers))
        chain.stop()

    def select_proxy(self, context: RequestContext) -> Optional[ProxyInstance]:
        """select a proxy responsible to forward a request to real AWS"""
        if not context.service:
            # this doesn't look like an AWS service invocation -> return
            return

        # reverse the list, to start with more recently added proxies first ...
        proxy_ports = reversed(self.PROXY_INSTANCES.keys())

        # find a matching proxy for this request
        for port in proxy_ports:
            proxy = self.PROXY_INSTANCES[port]
            proxy_config = proxy.get("config") or {}
            services = proxy_config.get("services") or {}
            service_name = self._get_canonical_service_name(context.service.service_name)
            service_config = services.get(service_name)
            if not service_config:
                continue

            # get resource name patterns
            resource_names = self._get_resource_names(service_config)

            # check if any resource name pattern matches
            resource_name_matches = any(
                self._request_matches_resource(context, resource_name_pattern)
                for resource_name_pattern in resource_names
            )
            if not resource_name_matches:
                continue

            # check if only read requests should be forwarded
            read_only = service_config.get("read_only")
            if read_only and not self._is_read_request(context):
                return

            # check if any operation name pattern matches
            operation_names = ensure_list(service_config.get("operations", []))
            operation_name_matches = any(
                re.match(op_name_pattern, context.operation.name)
                for op_name_pattern in operation_names
            )
            if operation_names and not operation_name_matches:
                continue

            # all checks passed -> return and use this proxy
            return proxy

    def _request_matches_resource(
        self, context: RequestContext, resource_name_pattern: str
    ) -> bool:
        try:
            service_name = self._get_canonical_service_name(context.service.service_name)
            if service_name == "s3":
                bucket_name = context.service_request.get("Bucket") or ""
                s3_bucket_arn = arns.s3_bucket_arn(bucket_name)
                return bool(re.match(resource_name_pattern, s3_bucket_arn))
            if service_name == "sqs":
                queue_name = context.service_request.get("QueueName") or ""
                queue_url = context.service_request.get("QueueUrl") or ""
                queue_name = queue_name or queue_url.split("/")[-1]
                candidates = (
                    queue_name,
                    queue_url,
                    sqs_queue_arn(
                        queue_name, account_id=context.account_id, region_name=context.region
                    ),
                )
                for candidate in candidates:
                    if re.match(resource_name_pattern, candidate):
                        return True
                return False
            if service_name == "secretsmanager":
                secret_id = context.service_request.get("SecretId") or ""
                secret_arn = secretsmanager_secret_arn(
                    secret_id, account_id=context.account_id, region_name=context.region
                )
                return bool(re.match(resource_name_pattern, secret_arn))
            # TODO: add more resource patterns
        except re.error as e:
            raise Exception(
                "Error evaluating regular expression - please verify proxy configuration"
            ) from e
        return True

    def forward_request(self, context: RequestContext, proxy: ProxyInstance) -> requests.Response:
        """Forward the given request to the proxy instance, and return the response."""
        port = proxy["port"]
        request = context.request
        target_host = get_addressable_container_host(default_local_hostname=LOCALHOST)
        url = f"http://{target_host}:{port}{request.path}?{to_str(request.query_string)}"

        # inject Auth header, to ensure we're passing the right region to the proxy (e.g., for Cognito InitiateAuth)
        self._extract_region_from_domain(context)
        headers = CaseInsensitiveDict(dict(request.headers))

        result = None
        try:
            headers[HEADER_HOST_ORIGINAL] = headers.pop("Host", None)
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
            # construct response
            result = requests.request(
                method=request.method, url=url, data=data, headers=dict(headers), stream=True
            )
            # TODO: ugly hack for now, simply attaching an additional attribute for raw response content
            result.raw_content = result.raw.read()
            # make sure we're removing any transfer-encoding headers
            result.headers.pop("Transfer-Encoding", None)
            LOG.debug(
                "Returned response: %s %s - %s",
                result.status_code,
                dict(result.headers),
                truncate(result.raw_content, max_length=500),
            )
        except requests.exceptions.ConnectionError:
            # remove unreachable proxy
            LOG.info("Removing unreachable AWS forward proxy due to connection issue: %s", url)
            self.PROXY_INSTANCES.pop(port, None)
        return result

    def _is_read_request(self, context: RequestContext) -> bool:
        """
        Function to determine whether a request is a read request.
        Note: Uses only simple heuristics, and may not be accurate for all services and operations!
        """
        operation_name = context.service_operation.operation
        if operation_name.lower().startswith(("describe", "get", "list", "query")):
            return True
        # service-specific rules
        if context.service.service_name == "cognito-idp" and operation_name == "InitiateAuth":
            return True
        if context.service.service_name == "dynamodb" and operation_name in {
            "Scan",
            "Query",
            "BatchGetItem",
            "PartiQLSelect",
        }:
            return True
        # TODO: add more rules
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
                    context.service.service_name,
                    region_name=part,
                    aws_access_key_id=TEST_AWS_ACCESS_KEY_ID,
                )
                return

    @classmethod
    def _get_resource_names(cls, service_config: ProxyServiceConfig) -> list[str]:
        """Get name patterns of resources to proxy from service config."""
        # match all by default
        default_names = [".*"]
        result = service_config.get("resources") or default_names
        return ensure_list(result)

    @classmethod
    def _get_canonical_service_name(cls, service_name: str) -> str:
        if service_name == "sqs-query":
            return "sqs"
        return service_name
