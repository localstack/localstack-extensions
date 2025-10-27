import boto3
import pytest
from botocore.exceptions import ClientError
from localstack.aws.connect import connect_to
from localstack.testing.config import TEST_AWS_ACCOUNT_ID
from localstack.utils.aws.arns import sqs_queue_arn, sqs_queue_url_for_arn

from aws_proxy.shared.models import ProxyConfig


def test_sqs_requests(start_aws_proxy, cleanups):
    queue_name_aws = "test-queue-aws"
    queue_name_local = "test-queue-local"

    # start proxy - only forwarding requests for queue name `test-queue-aws`
    config = ProxyConfig(services={"sqs": {"resources": f".*:{queue_name_aws}"}})
    start_aws_proxy(config)

    # create clients
    region_name = "us-east-1"
    sqs_client = connect_to(region_name=region_name).sqs
    sqs_client_aws = boto3.client("sqs", region_name=region_name)

    # create queue in AWS
    sqs_client_aws.create_queue(QueueName=queue_name_aws)
    queue_url_aws = sqs_client_aws.get_queue_url(QueueName=queue_name_aws)["QueueUrl"]
    queue_arn_aws = sqs_client_aws.get_queue_attributes(
        QueueUrl=queue_url_aws, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    cleanups.append(lambda: sqs_client_aws.delete_queue(QueueUrl=queue_url_aws))

    # assert that local call for this queue is proxied
    queue_local = sqs_client.get_queue_url(QueueName=queue_name_aws)
    assert queue_local["QueueUrl"]

    # create local queue
    sqs_client.create_queue(QueueName=queue_name_local)
    with pytest.raises(ClientError) as ctx:
        sqs_client_aws.get_queue_url(QueueName=queue_name_local)
    assert (
        ctx.value.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue"
    )

    # send message to AWS, receive locally
    sqs_client_aws.send_message(QueueUrl=queue_url_aws, MessageBody="message 1")
    received = sqs_client.receive_message(QueueUrl=queue_url_aws).get("Messages", [])
    assert len(received) == 1
    assert received[0]["Body"] == "message 1"
    sqs_client.delete_message(
        QueueUrl=queue_url_aws, ReceiptHandle=received[0]["ReceiptHandle"]
    )

    # send message locally, receive with AWS client
    sqs_client.send_message(QueueUrl=queue_url_aws, MessageBody="message 2")
    received = sqs_client_aws.receive_message(QueueUrl=queue_url_aws).get(
        "Messages", []
    )
    assert len(received) == 1
    assert received[0]["Body"] == "message 2"

    # assert that using a local queue URL also works for proxying
    queue_arn = sqs_queue_arn(
        queue_name_aws,
        account_id=TEST_AWS_ACCOUNT_ID,
        region_name=sqs_client.meta.region_name,
    )
    queue_url = sqs_queue_url_for_arn(queue_arn=queue_arn)
    result = sqs_client.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    assert result == queue_arn_aws
