import logging
from typing import Dict

import requests
from localstack import config
from localstack.aws.api import RequestContext
from localstack.aws.chain import Handler, HandlerChain
from localstack.constants import LOCALHOST
from localstack.http import Response

LOG = logging.getLogger(__name__)


class AwsProxyHandler(Handler):

    # maps port numbers to proxy instances
    PROXY_INSTANCES: Dict[int, Dict] = {}

    def __call__(self, chain: HandlerChain, context: RequestContext, response: Response):
        if not self.should_forward(context):
            return
        response = self.forward_request(context)
        if response is None:
            return
        # set response details, then stop handler chain to return response
        chain.response.data = response.content
        chain.response.status_code = response.status_code
        chain.response.headers.update(dict(response.headers))
        chain.stop()

    def should_forward(self, context: RequestContext) -> bool:
        if not self.PROXY_INSTANCES:
            return False
        # simple heuristic to determine whether a request should be forwarded to real AWS

        # TODO
        if context.service.service_name == "s3":
            return True

    def forward_request(self, context: RequestContext):
        proxy_instances = self.PROXY_INSTANCES
        port = next(iter(proxy_instances.keys()))
        target_host = config.DOCKER_HOST_FROM_CONTAINER if config.is_in_docker else LOCALHOST
        request = context.request
        url = f"http://{target_host}:{port}{request.path}"
        result = None
        try:
            result = requests.request(
                method=request.method, url=url, data=request.data, headers=request.headers
            )
        except requests.exceptions.ConnectionError:
            # remove unreachable proxy
            LOG.info("Removing unreachable AWS forward proxy due to connection issue: %s", url)
            proxy_instances.pop(port, None)
        return result
