import logging

from localstack.aws.chain import CompositeHandler
from localstack.extensions.api import Extension, http
from localstack.services.internal import get_internal_apis

LOG = logging.getLogger(__name__)


class AwsReplicatorExtension(Extension):
    name = "aws-replicator"

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from aws_replicator.config import HANDLER_PATH_PROXIES, HANDLER_PATH_REPLICATE
        from aws_replicator.server.request_handler import RequestHandler

        LOG.info("AWS resource replicator: adding routes to activate extension")
        endpoint = RequestHandler()
        get_internal_apis().add(HANDLER_PATH_REPLICATE, endpoint, methods=["POST"])
        get_internal_apis().add(HANDLER_PATH_PROXIES, endpoint, methods=["POST"])

    def update_request_handlers(self, handlers: CompositeHandler):
        from aws_replicator.server.aws_request_forwarder import AwsProxyHandler

        LOG.debug("AWS resource replicator: adding AWS proxy handler to the request chain")
        handlers.handlers.append(AwsProxyHandler())
