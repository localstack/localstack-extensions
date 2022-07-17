import json
import logging

import requests
from flask import Response as FlaskResponse
from localstack import config
from localstack.constants import LOCALHOST
from localstack.services.edge import PROXY_LISTENER_EDGE
from localstack.services.internal import get_internal_apis
from localstack.utils.patch import patch
from localstack.utils.strings import to_str
from requests import Response as RequestsResponse

LOG = logging.getLogger(__name__)


# TODO: outdated / not currently being used - needs to be adjusted to new Gateway


class AwsProxyInstancesResource:
    """Resource for the /_localstack/aws/proxies endpoint."""

    PROXY_INSTANCES = {}

    def on_post(self, request):
        data = json.loads(to_str(request.data))
        port = data["port"]
        self.PROXY_INSTANCES[port] = data
        return {}


def add_edge_routes():
    proxy_resource = AwsProxyInstancesResource()
    get_internal_apis().add("/aws/proxies", proxy_resource)

    def should_forward(result, method, path, data, headers) -> bool:
        if not AwsProxyInstancesResource.PROXY_INSTANCES:
            return False
        # simple heuristic to determine whether a request is "not found" and should be forwarded to real AWS
        not_found_codes = [400, 404]
        not_found_strings = ["does not exist", "ResourceNotFound"]
        try:
            status_code = content = result
            if isinstance(result, (RequestsResponse, FlaskResponse)):
                status_code = result.status_code
                content = result.content
            if status_code not in not_found_codes:
                return False
            data_str = str(content)
            return any(nfs in data_str for nfs in not_found_strings)
        except Exception:
            return False

    def forward_request(result, method, path, data, headers):
        proxy_instances = AwsProxyInstancesResource.PROXY_INSTANCES
        port = next(iter(proxy_instances.keys()))
        target_host = config.DOCKER_HOST_FROM_CONTAINER if config.is_in_docker else LOCALHOST
        url = f"http://{target_host}:{port}{path}"
        try:
            result = requests.request(method=method, url=url, data=data, headers=headers)
        except requests.exceptions.ConnectionError:
            # remove unreachable proxy
            LOG.info("Removing unreachable AWS forward proxy due to connection issue: %s", url)
            proxy_instances.pop(port, None)
        return result

    @patch(PROXY_LISTENER_EDGE.forward_request)
    def forward(self, fn, method, path, data, headers):
        result = fn(method, path, data, headers)
        if should_forward(result, method, path, data, headers):
            result = forward_request(result, method, path, data, headers)
        return result
