from typing import Union

from localstack.utils.functions import run_safe
from localstack.utils.strings import to_str, truncate


# TODO: add to common utils
def truncate_content(content: Union[str, bytes], max_length: int = None):
    max_length = max_length or 100
    if isinstance(content, bytes):
        content = run_safe(lambda: to_str(content)) or content
    return truncate(content, max_length=max_length)
