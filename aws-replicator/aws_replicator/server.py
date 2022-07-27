from localstack.http import Request
from localstack.http.dispatcher import Handler, ResultValue

from aws_replicator.replicate import ResourceReplicator
from aws_replicator.service_states import ReplicateStateRequest


class RequestHandler(Handler):
    def on_post(self, request: Request):
        return self.__call__(request)

    def __call__(self, request: Request, **kwargs) -> ResultValue:
        req = ReplicateStateRequest(**request.json)
        result = handle_replicate_request(req) or {}
        return result


def handle_replicate_request(request: ReplicateStateRequest):
    replicator = ResourceReplicator()
    return replicator.add_extended_resource_state(request, state=request["Properties"])
