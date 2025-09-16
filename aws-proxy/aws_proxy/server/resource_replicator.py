import logging
import os
from typing import Dict, Optional, Type

from localstack import config
from localstack.services.cloudformation.engine import template_deployer
from localstack.services.cloudformation.engine.entities import StackMetadata, StackTemplate
from localstack.services.cloudformation.provider import Stack
from localstack.utils.files import mkdir
from localstack.utils.run import run

from aws_replicator.client.service_states import ExtendedResourceStateReplicator
from aws_replicator.shared.models import ResourceReplicator
from aws_replicator.shared.utils import get_resource_type

LOG = logging.getLogger(__name__)

FORMER2_NPM_PACKAGE = "https://github.com/iann0036/former2"


# TODO see if we still need this class / unify
class ResourceReplicatorInternal(ResourceReplicator):
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

    def create_all(self):
        raise NotImplementedError

    def _get_cf_model_class(self, resource: Dict) -> Optional[Type]:
        res_type = get_resource_type(resource)
        return self._load_resource_models().get(res_type)

    def _load_resource_models(self):
        if not hasattr(template_deployer, "_ls_patch_applied"):
            try:
                from localstack.pro.core.services.cloudformation.cloudformation_extended import (
                    patch_cloudformation,
                )
            except ImportError:
                # TODO remove once we don't need compatibility with <3.6 anymore
                from localstack_ext.services.cloudformation.cloudformation_extended import (
                    patch_cloudformation,
                )

            patch_cloudformation()
            template_deployer._ls_patch_applied = True
        return template_deployer.RESOURCE_MODELS


class ResourceReplicatorFormer2(ResourceReplicator):
    """Resource replicator implementation based on the former2 project (https://github.com/iann0036/former2)"""

    def create(self, resource: Dict):
        raise NotImplementedError

    def create_all(self):
        cfn_template = self._run_former2_cli("generate")
        LOG.debug("Generated CloudFormation template: %s", cfn_template)
        # TODO: deploy template into LocalStack instance!

    def _run_former2_cli(self, *cmd_args) -> str:
        script_path = self._install()
        return run([script_path, *cmd_args])

    def _install(self) -> str:
        install_dir = os.path.join(config.dirs.var_libs, "former2")
        mkdir(install_dir)
        script_path = os.path.join(install_dir, "node_modules/.bin/former2")
        if not os.path.exists(script_path):
            run(["npm", "init", "-y"], cwd=install_dir)
            run(["npm", "i", FORMER2_NPM_PACKAGE], cwd=install_dir)
        return script_path
