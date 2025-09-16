import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict, Union

LOG = logging.getLogger(__name__)


class ReplicateStateRequest(TypedDict):
    """
    Represents a request sent from the CLI to the extension request
    handler to inject additional resource state properties.
    Using upper-case property names, to stay in line with CloudFormation/CloudControl resource models.
    """

    # resource type name (e.g., "AWS::S3::Bucket")
    Type: str
    # identifier of the resource
    PhysicalResourceId: Optional[str]
    # resource properties
    Properties: Dict[str, Any]


class ResourceReplicator(ABC):
    """
    Interface for resource replicator, to effect the creation of a cloned resource inside LocalStack.
    This interface has a client-side and a server-side implementation.
    """

    @abstractmethod
    def create(self, resource: Dict):
        """Create the resource specified via the given resource dict."""

    @abstractmethod
    def create_all(self):
        """Scrape and replicate all resources from the source AWS account into LocalStack."""


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
