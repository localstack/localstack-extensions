import json
import logging
from typing import Dict, Optional

import requests
from localstack import config
from localstack.aws.api import RequestContext
from localstack.aws.chain import Handler, HandlerChain
from localstack.constants import APPLICATION_JSON, LOCALHOST
from localstack.http import Response
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
        response = self.forward_request(context, proxy)
        if response is None:
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
        target_host = config.DOCKER_HOST_FROM_CONTAINER if config.is_in_docker else LOCALHOST
        request = context.request
        url = f"http://{target_host}:{port}{request.path}"
        result = None
        try:
            headers = CaseInsensitiveDict(dict(request.headers))
            headers.pop("Host", None)
            ctype = headers.get("Content-Type")
            data = b""
            if ctype == APPLICATION_JSON:
                data = json.dumps(request.json)
            elif request.form:
                data = request.form
            elif request.data:
                data = request.data
            result = requests.request(
                method=request.method, url=url, data=data, headers=dict(headers)
            )
        except requests.exceptions.ConnectionError:
            # remove unreachable proxy
            LOG.info("Removing unreachable AWS forward proxy due to connection issue: %s", url)
            self.PROXY_INSTANCES.pop(port, None)
        return result
