from localstack.http import Request
from localstack.http.dispatcher import Handler, ResultValue

from aws_replicator.config import HANDLER_PATH_PROXIES
from aws_replicator.server.aws_request_forwarder import AwsProxyHandler
from aws_replicator.server.resource_replicator import ResourceReplicatorServer
from aws_replicator.shared.models import AddProxyRequest, ReplicateStateRequest


class RequestHandler(Handler):
    def on_post(self, request: Request):
        return self.__call__(request)

    def __call__(self, request: Request, **kwargs) -> ResultValue:
        if HANDLER_PATH_PROXIES in request.path:
            req = AddProxyRequest(**request.json)
            result = handle_proxies_request(req)
        else:
            req = ReplicateStateRequest(**request.json)
            result = handle_replicate_request(req)
        return result or {}


def handle_replicate_request(request: ReplicateStateRequest):
    replicator = ResourceReplicatorServer()
    return replicator.create(request)


def handle_proxies_request(request: AddProxyRequest):
    AwsProxyHandler.PROXY_INSTANCES[request["port"]] = request
    return {}
