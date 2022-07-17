import json

from localstack.http import Request, Response

from aws_replicator.replicate import ResourceReplicator
from aws_replicator.service_states import ReplicateStateRequest


class RequestHandler:
    def __call__(self, request: Request, **kwargs) -> Response:
        if request.method != "POST":
            return Response(status=404)
        content = request.json
        print(content)
        req = ReplicateStateRequest(**content)
        result = handle_replicate_request(req) or {}
        return Response(json.dumps(result))


def handle_replicate_request(request: ReplicateStateRequest):
    replicator = ResourceReplicator()
    replicator.add_extended_resource_state(request, state=request["Properties"])
