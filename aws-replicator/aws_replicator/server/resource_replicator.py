import logging
from typing import Dict, Optional, Type

from localstack.services.cloudformation.engine import template_deployer
from localstack.services.cloudformation.engine.entities import StackMetadata, StackTemplate
from localstack.services.cloudformation.provider import Stack

from aws_replicator.client.service_states import ExtendedResourceStateReplicator
from aws_replicator.shared.models import ResourceReplicator
from aws_replicator.shared.utils import get_resource_type

LOG = logging.getLogger(__name__)


class ResourceReplicatorServer(ResourceReplicator):
    """Utility that creates resources from CloudFormation/CloudControl templates."""

    def create(self, resource: Dict):
        cf_model_class = self._get_cf_model_class(resource)
        if not cf_model_class:
            return

        if resource.get("TypeName") and not resource.get("Type"):
            resource["Type"] = resource.pop("TypeName")

        res_type = get_resource_type(resource)
        res_json = {"Type": res_type, "Properties": resource["Properties"]}
        LOG.debug("Deploying CloudFormation resource: %s", res_json)

        # note: quick hack for now - creating a fake Stack for each individual resource to be deployed
        template = StackTemplate(StackName="s1", Resources={"myres": res_json})
        metadata = StackMetadata(StackName="s1")
        stack = Stack(metadata, template=template)
        resource_status = template_deployer.retrieve_resource_details(
            "myres", {}, stack.resources, stack_name=stack.stack_name
        )

        if not resource_status:
            # deploy resource, if it doesn't exist yet
            deployer = template_deployer.TemplateDeployer(stack)
            deployer.deploy_stack()
            # TODO: need to ensure that the ID of the created resource also matches!

        # add extended state (e.g., actual S3 objects)

        model_instance = ExtendedResourceStateReplicator.get_resource_instance(resource)
        if not model_instance:
            res_type = get_resource_type(resource)
            LOG.info("Unable to find CloudFormation model class for resource: %s", res_type)
            return
        return model_instance.add_extended_state_internal(resource["Properties"])

    def _get_cf_model_class(self, resource: Dict) -> Optional[Type]:
        res_type = get_resource_type(resource)
        return load_resource_models().get(res_type)


def load_resource_models():
    if not hasattr(template_deployer, "_ls_patch_applied"):
        from localstack_ext.services.cloudformation.cloudformation_extended import (
            patch_cloudformation,
        )

        patch_cloudformation()
        template_deployer._ls_patch_applied = True
    return template_deployer.RESOURCE_MODELS
