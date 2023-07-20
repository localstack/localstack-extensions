from typing import Any, Callable, Dict, Optional


def list_all_resources(
    page_function: Callable[[dict], Any],
    last_token_attr_name: str,
    list_attr_name: str,
    next_token_attr_name: Optional[str] = None,
    max_pages=None,
) -> list:
    if next_token_attr_name is None:
        next_token_attr_name = last_token_attr_name

    result = None
    collected_items = []
    last_evaluated_token = None

    pages = 0
    while not result or last_evaluated_token:
        if max_pages and pages >= max_pages:
            break
        kwargs = {next_token_attr_name: last_evaluated_token} if last_evaluated_token else {}
        result = page_function(kwargs)
        last_evaluated_token = result.get(last_token_attr_name)
        collected_items += result.get(list_attr_name, [])
        pages += 1

    return collected_items


def get_resource_type(resource: Dict) -> str:
    return resource.get("Type") or resource.get("TypeName")
