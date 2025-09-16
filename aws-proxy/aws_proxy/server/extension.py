import logging

from localstack import config
from localstack.aws.chain import CompositeHandler
from localstack.extensions.api import Extension, http
from localstack.services.internal import get_internal_apis

LOG = logging.getLogger(__name__)


class AwsProxyExtension(Extension):
    name = "aws-proxy"

    def on_extension_load(self):
        if config.GATEWAY_SERVER == "twisted":
            LOG.warning(
                "AWS Proxy: The aws-proxy extension currently requires hypercorn as "
                "gateway server. Please start localstack with GATEWAY_SERVER=hypercorn"
            )

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from aws_proxy.server.request_handler import RequestHandler

        LOG.info("AWS Proxy: adding routes to activate extension")
        get_internal_apis().add(RequestHandler())

    def update_request_handlers(self, handlers: CompositeHandler):
        from aws_proxy.server.aws_request_forwarder import AwsProxyHandler

        LOG.debug("AWS Proxy: adding AWS proxy handler to the request chain")
        handlers.handlers.append(AwsProxyHandler())
