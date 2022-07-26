import logging

from localstack.extensions.api import Extension, http
from localstack.services.internal import get_internal_apis

LOG = logging.getLogger(__name__)


class AwsReplicatorExtension(Extension):
    name = "aws-replicator"

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from aws_replicator.config import HANDLER_PATH
        from aws_replicator.server import RequestHandler

        LOG.info("AWS resource replicator: adding routes to activate extension")
        endpoint = RequestHandler()
        get_internal_apis().add(HANDLER_PATH, endpoint, methods=["POST"])
