import logging
from typing import Dict, List, TypedDict, Union

LOG = logging.getLogger(__name__)


class ProxyServiceConfig(TypedDict, total=False):
    # list of regexes identifying resources to be proxied requests to
    resources: Union[str, List[str]]
    # list of operation names (regexes) that should be proxied
    operations: List[str]
    # whether only read requests should be forwarded
    read_only: bool


class ProxyConfig(TypedDict, total=False):
    # maps service name to service proxy configs
    services: Dict[str, ProxyServiceConfig]
    # bind host for the proxy (defaults to 127.0.0.1)
    bind_host: str


class ProxyInstance(TypedDict):
    """Represents a proxy instance"""

    # port of the proxy on the host
    port: int
    # configuration for the proxy
    config: ProxyConfig


class AddProxyRequest(ProxyInstance):
    """
    Represents a request to register a new local proxy instance with the extension inside LocalStack.
    """

    env_vars: dict
