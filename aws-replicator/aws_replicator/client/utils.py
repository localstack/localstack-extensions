from typing import Union

import requests
from localstack.config import get_edge_url
from localstack.utils.functions import run_safe
from localstack.utils.strings import to_str, truncate

from aws_replicator.config import HANDLER_PATH_REPLICATE
from aws_replicator.shared.models import ReplicateStateRequest


def post_request_to_instance(request: ReplicateStateRequest = None):
    url = f"{get_edge_url()}{HANDLER_PATH_REPLICATE}"
    response = requests.post(url, json=request or {})
    if not response.ok:
        raise Exception(f"Invocation failed (code {response.status_code}): {response.content}")
    return response


# TODO: add to common utils
def truncate_content(content: Union[str, bytes], max_length: int = None):
    max_length = max_length or 100
    if isinstance(content, bytes):
        content = run_safe(lambda: to_str(content)) or content
    return truncate(content, max_length=max_length)
