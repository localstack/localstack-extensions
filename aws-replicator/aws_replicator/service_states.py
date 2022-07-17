import json
import logging
from typing import Any, Dict, Type, TypedDict

import boto3
import requests
from localstack.config import get_edge_url
from localstack.constants import INTERNAL_RESOURCE_PATH
from localstack.services.cloudformation.models.dynamodb import DynamoDBTable
from localstack.services.cloudformation.models.s3 import S3Bucket
from localstack.services.cloudformation.models.sqs import SQSQueue
from localstack.utils.aws import aws_stack
from localstack.utils.cloudformation import template_deployer
from localstack.utils.threads import parallelize

from aws_replicator.config import HANDLER_PATH

LOG = logging.getLogger(__name__)


# TODO: move to patch utils
def extend(clazz: Type, method_name: str = None):
    def wrapper(fn):
        method = method_name or fn.__name__
        setattr(clazz, method, fn)

    return wrapper


class ReplicateStateRequest(TypedDict):
    # resource type name (e.g., "AWS::S3::Bucket")
    Type: str
    # identifier of the resource
    PhysicalResourceId: str
    # resource properties
    Properties: Dict[str, Any]


def load_resource_models():
    if not hasattr(template_deployer, "_ls_patch_applied"):
        from localstack_ext.services.cloudformation.cloudformation_extended import (
            patch_cloudformation,
        )

        patch_cloudformation()
        template_deployer._ls_patch_applied = True
    return template_deployer.RESOURCE_MODELS


# resource-specific replications


@extend(SQSQueue, "add_extended_state")
def sqs_add_extended_state(self, state: Dict = None):
    queue_name = self.props["QueueName"]

    if state is None:
        # executing in the context of the CLI

        remote = boto3.client("sqs")
        queue_url = remote.get_queue_url(QueueName=queue_name)["QueueUrl"]

        messages = []
        while True:
            response = remote.receive_message(QueueUrl=queue_url, WaitTimeSeconds=1)
            msgs = response.get("Messages")
            if not msgs:
                break
            messages.extend(msgs)

        state = {**self.props, "Messages": messages}
        request = ReplicateStateRequest(
            Type=self.cloudformation_type(),
            Properties=state,
            PhysicalResourceId=queue_url,
        )
        _post_request(request)
        return

    # executing in the context of the server
    from localstack.aws.api.sqs import Message
    from localstack.services.sqs.provider import SqsBackend

    messages = state.get("Messages") or []
    LOG.info("Inserting %s messages into queue", len(messages), queue_name)
    for region, details in SqsBackend.regions().items():
        queue = details.queues.get(queue_name)
        if not queue:
            continue
        for message in messages:
            message.setdefault("MD5OfMessageAttributes", None)
            queue.put(Message(**message))
        break


@extend(DynamoDBTable, "add_extended_state")
def dynamodb_add_extended_state(self, state: Dict = None):
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
def s3_add_extended_state(self, state: Dict = None):
    bucket_name = self.props["BucketName"]
    LOG.debug("Copying items from source S3 bucket '%s' into target", bucket_name)

    remote = boto3.resource("s3")
    local = aws_stack.connect_to_resource("s3")
    remote_bucket = remote.Bucket(bucket_name)
    local_bucket = local.Bucket(bucket_name)
    # TODO: make configurable
    max_object_size = 1000 * 1000

    def copy_object(obj):
        if obj.size > max_object_size:
            LOG.debug("Skip copying large S3 object %s with %s bytes", obj.key, obj.size)
            return
        local_bucket.put_object(Key=obj.key, Body=obj.get()["Body"].read())

    parallelize(copy_object, list(remote_bucket.objects.all()), size=15)


def _post_request(request: ReplicateStateRequest):
    url = f"{get_edge_url()}{INTERNAL_RESOURCE_PATH}{HANDLER_PATH}"
    response = requests.post(url, data=json.dumps(request))
    assert response.ok
    return response
