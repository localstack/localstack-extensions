import json
import logging
import os
import threading
from copy import deepcopy
from typing import Dict, List, Type

import boto3
from localstack.services.cloudformation.models.dynamodb import DynamoDBTable
from localstack.services.cloudformation.models.s3 import S3Bucket
from localstack.services.cloudformation.models.sqs import SQSQueue
from localstack.services.cloudformation.provider import Stack
from localstack.utils.aws import aws_stack
from localstack.utils.cloudformation import template_deployer
from localstack.utils.cloudformation.template_deployer import canonical_resource_type
from localstack.utils.collections import select_attributes
from localstack.utils.files import load_file, save_file
from localstack.utils.json import extract_jsonpath
from localstack.utils.testutil import list_all_resources
from localstack.utils.threads import parallelize

# from localstack_ext.services.cloudformation.cloudformation_extended import patch_cloudformation

LOG = logging.getLogger(__name__)


# additional service resources that are currently not yet supported by Cloud Control
SERVICE_RESOURCES = {
    "DynamoDB::Table": {
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
                {"BillingMode": "PAY_PER_REQUEST"},
                "$.Table.StreamSpecification",
                "$.Table.Tags",
                "$.Table.TableClass",
            ],
        },
    },
}

# TODO: hack for now, to reduce the search time
TMP_RESOURCE_TYPES = [
    # "AWS::Athena::WorkGroup", "AWS::Athena::DataCatalog", "AWS::CloudFront::Distribution",
    # "AWS::DynamoDB::Table",
    # "AWS::EC2::VPC",
    # "AWS::Lambda::EventSourceMapping",
    # "AWS::Lambda::Function",
    "AWS::S3::Bucket",
    # "AWS::SQS::Queue",
    # "AWS::IAM::Role",
]


class AwsAccountScraper:
    """Scrapes and returns the resources in the AWS account targeted by a given boto3 session"""

    def __init__(self, session: boto3.Session):
        self.session = session

    def get_resource_types(self) -> List[Dict]:
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
            res_type = canonical_resource_type(res_type)
            existing = [ts for ts in all_types if ts["TypeName"] == res_type]
            if not existing:
                all_types.append({"TypeName": res_type})

        return all_types

    def get_resources(self, resource_type: str) -> List[Dict]:
        result = []
        result += self.get_resources_cloudcontrol(resource_type)
        result += self.get_resources_custom(resource_type)
        return result

    def get_resources_cloudcontrol(self, resource_type: str) -> List[Dict]:
        cloudcontrol = self.session.client("cloudcontrol")
        try:
            # fetch the list of resource identifiers
            res_list = list_all_resources(
                lambda kwargs: cloudcontrol.list_resources(TypeName=resource_type),
                last_token_attr_name="NextToken",
                list_attr_name="ResourceDescriptions",
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

        resource_type = (
            f"AWS::{resource_type}" if not resource_type.startswith("AWS::") else resource_type
        )
        model_class = _load_resource_models().get(resource_type)
        if not model_class:
            return []

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
            props_mapping = details.get("props")
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
                    else:
                        field_name = res_field.split(".")[-1]
                        field_value = extract_jsonpath(res_details, res_field)
                    if field_value != []:
                        props[field_name] = field_value

            res_json = {"Type": resource_type, "Properties": props}
            result.append(res_json)

        return result


class ResourceReplicator:
    """Utility that creates resources from CloudFormation/CloudControl templates."""

    def create(self, resource: Dict):
        model_class = self._get_resource_model(resource)
        if not model_class:
            return

        res_type = self._resource_type(resource)
        res_json = {"Type": res_type, "Properties": resource["Properties"]}
        LOG.debug("Deploying CloudFormation resource: %s", res_json)

        # note: quick hack for now - creating a fake Stack for each individual resource to be deployed
        stack = Stack({"StackName": "s1"})
        stack.template_resources["myres"] = res_json
        resource_status = template_deployer.retrieve_resource_details("myres", {}, stack)

        if not resource_status:
            # deploy resource, if it doesn't exist yet
            template_deployer.deploy_resource(stack, "myres")
            # TODO: need to ensure that the ID of the created resource also matches!

        # add extended state (e.g., actual S3 objects)
        self._add_extended_resource_state(res_json)

    def _add_extended_resource_state(self, resource: Dict):
        model_class = self._get_resource_model(resource)
        if not hasattr(model_class, "add_extended_state"):
            return
        model_instance = model_class(resource)
        model_instance.add_extended_state()

    def _resource_type(self, resource: Dict) -> str:
        res_type = resource.get("Type") or resource["TypeName"]
        return canonical_resource_type(res_type)

    def _get_resource_model(self, resource: Dict) -> str:
        res_type = self._resource_type(resource)
        model_class = _load_resource_models().get(res_type)
        if not model_class:
            LOG.info("Unable to find CloudFormation model class for resource: %s", res_type)
        return model_class


def _load_resource_models():
    if not hasattr(template_deployer, "_ls_patch_applied"):
        patch_cloudformation()
        template_deployer._ls_patch_applied = True
    return template_deployer.RESOURCE_MODELS


def replicate_state(scraper: AwsAccountScraper, creator: ResourceReplicator):
    """Replicate the state from a source AWS account into a target account (or LocalStack)"""

    res_types = scraper.get_resource_types()
    LOG.info("Found %s Cloud Control resources types", len(res_types))

    for res_type in res_types:
        type_name = res_type["TypeName"]
        if TMP_RESOURCE_TYPES and type_name not in TMP_RESOURCE_TYPES:
            continue
        resources = scraper.get_resources(type_name)
        LOG.info("Found %s resources of type %s", len(resources), type_name)
        for resource in resources:
            creator.create(resource)


def replicate_state_into_local():
    scraper = AwsAccountScraper(boto3.Session())
    creator = ResourceReplicator()
    return replicate_state(scraper, creator)


# resource-specific replications


# TODO: move to patch utils
def extend(clazz: Type, method_name: str = None):
    def wrapper(fn):
        method = method_name or fn.__name__
        setattr(clazz, method, fn)
    return wrapper


@extend(SQSQueue, "add_extended_state")
def sqs_add_extended_state(self):
    print("!!SQS add_extended_state", self)
    # TODO: add messages to queues


@extend(DynamoDBTable, "add_extended_state")
def dynamodb_add_extended_state(self):
    table_name = self.props["TableName"]
    LOG.debug("Copying items from source table '%s' into target", table_name)

    remote = boto3.resource("dynamodb")
    local = aws_stack.connect_to_resource("dynamodb")
    remote_table = remote.Table(table_name)
    local_table = local.Table(table_name)

    first_request = True
    response = {}
    while first_request or "LastEvaluatedKey" in response:
        kwargs = {} if first_request else {"ExclusiveStartKey": response["LastEvaluatedKey"]}
        first_request = False
        response = remote_table.scan(**kwargs)
        with local_table.batch_writer() as batch:
            for item in response["Items"]:
                batch.put_item(Item=item)


@extend(S3Bucket, "add_extended_state")
def s3_add_extended_state(self):
    bucket_name = self.props["BucketName"]
    LOG.debug("Copying items from source S3 bucket '%s' into target", bucket_name)

    remote = boto3.resource("s3")
    local = aws_stack.connect_to_resource("s3")
    remote_bucket = remote.Bucket(bucket_name)
    local_bucket = local.Bucket(bucket_name)
    max_object_size = 1000 * 1000

    def copy_object(obj):
        if obj.size > max_object_size:
            LOG.debug("Skip copying large S3 object %s with %s bytes", obj.key, obj.size)
            return
        local_bucket.put_object(Key=obj.key, Body=obj.get()["Body"].read())

    parallelize(copy_object, list(remote_bucket.objects.all()), size=15)
