from localstack.extensions.api import Extension, http

from aws_replicator.config import HANDLER_PATH
from aws_replicator.server import RequestHandler


class AwsReplicatorExtension(Extension):
    name = "aws-replicator"

    def on_platform_start(self):
        print("AWS replicator: LocalStack is starting!")

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        endpoint = RequestHandler()
        router.add(HANDLER_PATH, endpoint=endpoint)
