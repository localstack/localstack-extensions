import json

from localstack.http import Request, Response

from aws_replicator.replicate import ResourceReplicator
from aws_replicator.service_states import ReplicateStateRequest


class RequestHandler:
    def on_post(self, request: Request):
        return self.__call__(request)

    def __call__(self, request: Request, **kwargs) -> Response:
        if request.method != "POST":
            return Response(status=404)
        content = json.loads(request.get_data(as_text=True))
        req = ReplicateStateRequest(**content)
        result = handle_replicate_request(req) or {}
        return Response(json.dumps(result))


def handle_replicate_request(request: ReplicateStateRequest):
    replicator = ResourceReplicator()
    return replicator.add_extended_resource_state(request, state=request["Properties"])
