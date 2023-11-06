import json
import logging
import os
import threading
from copy import deepcopy
from typing import Dict, List

import boto3
from localstack.utils.collections import select_attributes
from localstack.utils.files import load_file, save_file
from localstack.utils.json import extract_jsonpath
from localstack.utils.threads import parallelize

from aws_replicator.client.utils import post_request_to_instance
from aws_replicator.shared.models import (
    ExtendedResourceStateReplicator,
    ReplicateStateRequest,
    ResourceReplicator,
)
from aws_replicator.shared.utils import list_all_resources

LOG = logging.getLogger(__name__)

# maximum number of pages to fetch for paginated APIs
MAX_PAGES = 3

# additional service resources that are currently not yet supported by Cloud Control
SERVICE_RESOURCES = {
    "AWS::DynamoDB::Table": {
        "list_operation": "list_tables",
        "results": "$.TableNames",
        "fetch_details": {
            "operation": "describe_table",
            "parameters": {"TableName": "$"},
            "results": [
                "$.Table.AttributeDefinitions",
                "$.Table.TableName",
                "$.Table.KeySchema",
                "$.Table.LocalSecondaryIndexes",
                "$.Table.GlobalSecondaryIndexes",
                {
                    "GlobalSecondaryIndexes": lambda params: [
                        select_attributes(p, ["IndexName", "KeySchema", "Projection"])
                        for p in params["Table"].get("GlobalSecondaryIndexes", [])
                    ]
                },
                {"BillingMode": "PAY_PER_REQUEST"},
                "$.Table.StreamSpecification",
                "$.Table.Tags",
                "$.Table.TableClass",
            ],
        },
    },
    "AWS::SSM::Parameter": {
        "list_operation": "describe_parameters",
        "results": "$.Parameters",
        "fetch_details": {
            "operation": "get_parameter",
            "parameters": {"Name": "$.Name"},
            "results": [
                "$.Parameter.Name",
                "$.Parameter.Type",
                "$.Parameter.Value",
            ],
        },
    },
}


class AwsAccountScraper:
    """Scrapes and returns the resources in the AWS account targeted by a given boto3 session"""

    def __init__(self, session: boto3.Session):
        self.session = session

    def get_resource_types(self) -> List[Dict]:
        """Return a list of supported resource types for scraping an AWS account"""

        res_types_file = os.path.join(os.path.dirname(__file__), "resource_types.json")
        if os.path.exists(res_types_file):
            # load cached resources file
            all_types = json.loads(load_file(res_types_file))
        else:
            cloudformation = self.session.client("cloudformation")
            all_types = list_all_resources(
                lambda kwargs: cloudformation.list_types(
                    Type="RESOURCE",
                    Visibility="PUBLIC",
                    ProvisioningType="FULLY_MUTABLE",
                    MaxResults=100,
                    **kwargs,
                ),
                last_token_attr_name="NextToken",
                list_attr_name="TypeSummaries",
            )
            all_types = [select_attributes(ts, ["TypeName"]) for ts in all_types]
            # update cached resources file
            save_file(res_types_file, json.dumps(all_types))

        # add custom resource types
        for res_type, details in SERVICE_RESOURCES.items():
            existing = [ts for ts in all_types if ts["TypeName"] == res_type]
            if not existing:
                all_types.append({"TypeName": res_type})

        return all_types

    def get_resources(self, resource_type: str) -> List[Dict]:
        result = []
        try:
            result += self.get_resources_cloudcontrol(resource_type)
            result += self.get_resources_custom(resource_type)
        except Exception as e:
            LOG.info("Unable to fetch resources of type %s: %s", resource_type, e)
        return result

    def get_resources_cloudcontrol(self, resource_type: str) -> List[Dict]:
        cloudcontrol = self.session.client("cloudcontrol")
        try:
            # fetch the list of resource identifiers
            res_list = list_all_resources(
                lambda kwargs: cloudcontrol.list_resources(TypeName=resource_type),
                last_token_attr_name="NextToken",
                list_attr_name="ResourceDescriptions",
                max_pages=MAX_PAGES,
            )

            # fetch the detailed resource descriptions

            def handle(resource):
                cloudcontrol = self.session.client("cloudcontrol")
                res_details = cloudcontrol.get_resource(
                    TypeName=resource_type, Identifier=resource["Identifier"]
                )
                with lock:
                    resources.append(res_details)

            # parallelizing the execution, as CloudControl can be very slow to respond
            lock = threading.RLock()
            resources = []
            parallelize(handle, res_list)

            result = [
                {
                    "TypeName": resource_type,
                    "Identifier": r["ResourceDescription"]["Identifier"],
                    "Properties": json.loads(r["ResourceDescription"]["Properties"]),
                }
                for r in resources
            ]
            return result
        except Exception as e:
            exs = str(e)
            if "UnsupportedActionException" in exs:
                LOG.info("Unsupported operation: %s", e)
                return []
            if "must not be null" in exs or "cannot be empty" in exs:
                LOG.info("Unable to list resources: %s", e)
                return []
            LOG.warning("Unknown error occurred: %s", e)
            return []

    def get_resources_custom(self, resource_type: str) -> List[Dict]:
        resource_type_short = resource_type.removeprefix("AWS::")
        details = SERVICE_RESOURCES.get(resource_type_short)
        if not details:
            return []

        from localstack.services.cloudformation.engine import template_deployer

        service_name = template_deployer.get_service_name({"Type": resource_type})
        from_client = boto3.client(service_name)

        res_list = getattr(from_client, details["list_operation"])()

        res_selector = details.get("results")
        if res_selector:
            res_list = extract_jsonpath(res_list, res_selector)

        res_list = res_list or []
        result = []
        for _resource in res_list:
            props = {}
            props_mapping = details.get("props") or {}
            for prop_key, prop_val in props_mapping.items():
                if "$" in prop_val:
                    props[prop_key] = extract_jsonpath(_resource, prop_val)

            fetch_details = details.get("fetch_details")
            if fetch_details:
                params = deepcopy(fetch_details.get("parameters") or {})
                for param, param_value in params.items():
                    if "$" in param_value:
                        params[param] = extract_jsonpath(_resource, param_value)
                res_details = getattr(from_client, fetch_details["operation"])(**params)
                res_fields = fetch_details.get("results")
                for res_field in res_fields:
                    if isinstance(res_field, dict):
                        field_name = list(res_field.keys())[0]
                        field_value = list(res_field.values())[0]
                        if callable(field_value):
                            field_value = field_value(res_details)
                    else:
                        field_name = res_field.split(".")[-1]
                        field_value = extract_jsonpath(res_details, res_field)
                    if field_value != []:
                        props[field_name] = field_value

            res_json = {"Type": resource_type, "Properties": props}
            result.append(res_json)

        return result


class ResourceReplicatorClient(ResourceReplicator):
    def create(self, resource: Dict):
        # request creation via server
        request = ReplicateStateRequest(**resource)
        post_request_to_instance(request)

        # add extended state attributes
        model_instance = ExtendedResourceStateReplicator.get_resource_instance(resource)
        if model_instance:
            model_instance.add_extended_state_external()

    def create_all(self):
        # request creation
        post_request_to_instance()


def replicate_state_with_scraper_on_host(
    scraper: AwsAccountScraper, creator: ResourceReplicator, services: List[str] = None
):
    """Replicate the state from a source AWS account into a target account (or LocalStack)"""

    res_types = scraper.get_resource_types()
    LOG.info("Found %s Cloud Control resources types", len(res_types))

    for res_type in res_types:
        type_name = res_type["TypeName"]
        if services:
            service_name = type_name.removeprefix("AWS::").lower().split("::")[0]
            if service_name not in services:
                continue
        resources = scraper.get_resources(type_name)
        LOG.info("Found %s resources of type %s", len(resources), type_name)
        for resource in resources:
            creator.create(resource)


def replicate_state_with_scraper_in_container(
    creator: ResourceReplicator, services: List[str] = None
):
    """Replicate the state from a source AWS account into a target account (or LocalStack)"""
    creator.create_all()


def replicate_state_into_local(services: List[str]):
    creator = ResourceReplicatorClient()

    # deprecated
    # scraper = AwsAccountScraper(boto3.Session())
    # return replicate_state_with_scraper_on_host(scraper, creator, services=services)

    return replicate_state_with_scraper_in_container(creator, services=services)
