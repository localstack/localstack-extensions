import requests
from localstack.config import get_edge_url
from localstack.constants import INTERNAL_RESOURCE_PATH

from aws_replicator.config import HANDLER_PATH
from aws_replicator.shared.models import ReplicateStateRequest


def post_request_to_instance(request: ReplicateStateRequest):
    url = f"{get_edge_url()}{INTERNAL_RESOURCE_PATH}{HANDLER_PATH}"
    response = requests.post(url, json=request)
    assert response.ok
    return response
