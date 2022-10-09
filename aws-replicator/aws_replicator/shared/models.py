import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypedDict

from botocore.client import BaseClient
from localstack.services.cloudformation.service_models import GenericBaseModel
from localstack.utils.objects import get_all_subclasses

LOG = logging.getLogger(__name__)


class ExtendedResourceStateReplicator(GenericBaseModel):
    """Extended resource models, used to replicate (inject) additional state into a resource instance"""

    def add_extended_state_external(self, remote_client: BaseClient = None):
        """Called in the context of external CLI execution to fetch/replicate resource details from a remote account"""

    def add_extended_state_internal(self, state: Dict):
        """Called in the context of the internal LocalStack instance to inject the state into a resource"""

    @classmethod
    def get_resource_instance(cls, resource: Dict) -> Optional["ExtendedResourceStateReplicator"]:
        resource_class = cls.find_resource_classes().get(resource["Type"])
        if resource_class:
            return resource_class(resource)

    @classmethod
    def get_resource_class(
        cls, resource_type: str
    ) -> Optional[Type["ExtendedResourceStateReplicator"]]:
        return cls.find_resource_classes().get(resource_type)

    @classmethod
    def find_resource_classes(cls) -> Dict[str, "ExtendedResourceStateReplicator"]:
        return {
            inst.cloudformation_type(): inst
            for inst in get_all_subclasses(ExtendedResourceStateReplicator)
        }


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


class ProxyInstance(TypedDict):
    """Represents a proxy instance"""

    # port of the proxy on the host
    port: int
    # name of AWS services to proxy
    services: List[str]


class AddProxyRequest(ProxyInstance):
    """
    Represents a request to register a new local proxy instance with the extension inside LocalStack.
    """
