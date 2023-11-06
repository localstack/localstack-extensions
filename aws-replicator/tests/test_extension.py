# Note: these tests depend on the extension being installed and actual AWS credentials being configured, such
# that the proxy can be started within the tests. They are designed to be mostly run in CI at this point.
import gzip

import boto3
import pytest
from botocore.exceptions import ClientError
from localstack.aws.connect import connect_to
from localstack.constants import TEST_AWS_ACCOUNT_ID
from localstack.utils.aws.arns import sqs_queue_arn, sqs_queue_url_for_arn
from localstack.utils.net import wait_for_port_open
from localstack.utils.sync import retry

from aws_replicator.client.auth_proxy import start_aws_auth_proxy
from aws_replicator.shared.models import ProxyConfig


@pytest.fixture
def start_aws_proxy():
    proxies = []

    def _start(config: dict = None):
        proxy = start_aws_auth_proxy(config)
        wait_for_port_open(proxy.port)
        proxies.append(proxy)
        return proxy

    yield _start

    for proxy in proxies:
        proxy.shutdown()


@pytest.mark.parametrize("metadata_gzip", [True, False])
def test_s3_requests(start_aws_proxy, s3_create_bucket, metadata_gzip):
    # start proxy
    config = ProxyConfig(services={"s3": {"resources": ".*"}})
    start_aws_proxy(config)

    # create clients
    s3_client = connect_to().s3
    s3_client_aws = boto3.client("s3")

    # list buckets to assert that proxy is up and running
    buckets_proxied = s3_client.list_buckets()["Buckets"]
    bucket_aws = s3_client_aws.list_buckets()["Buckets"]
    assert buckets_proxied == bucket_aws

    # create bucket
    bucket = s3_create_bucket()
    buckets_proxied = s3_client.list_buckets()["Buckets"]
    bucket_aws = s3_client_aws.list_buckets()["Buckets"]
    assert buckets_proxied and buckets_proxied == bucket_aws

    # put object
    key = "test-key-with-urlencoded-chars-:+"
    body = b"test 123"
    kwargs = {}
    if metadata_gzip:
        kwargs = {"ContentEncoding": "gzip", "ContentType": "text/plain"}
        body = gzip.compress(body)
    s3_client.put_object(Bucket=bucket, Key=key, Body=body, **kwargs)

    # get object
    result = s3_client.get_object(Bucket=bucket, Key=key)
    result_body_proxied = result["Body"].read()
    result = s3_client_aws.get_object(Bucket=bucket, Key=key)
    result_body_aws = result["Body"].read()
    assert result_body_proxied == result_body_aws

    for kwargs in [{}, {"Delimiter": "/"}]:
        # list objects
        result_aws = s3_client_aws.list_objects(Bucket=bucket, **kwargs)
        result_proxied = s3_client.list_objects(Bucket=bucket, **kwargs)
        assert result_proxied["Contents"] == result_aws["Contents"]

        # list objects v2
        result_aws = s3_client_aws.list_objects_v2(Bucket=bucket, **kwargs)
        result_proxied = s3_client.list_objects_v2(Bucket=bucket, **kwargs)
        assert result_proxied["Contents"] == result_aws["Contents"]

    # delete object
    s3_client.delete_object(Bucket=bucket, Key=key)
    with pytest.raises(ClientError) as aws_exc:
        s3_client_aws.get_object(Bucket=bucket, Key=key)
    with pytest.raises(ClientError) as exc:
        s3_client.get_object(Bucket=bucket, Key=key)
    assert str(exc.value) == str(aws_exc.value)

    # delete bucket
    s3_client_aws.delete_bucket(Bucket=bucket)

    def _assert_deleted():
        with pytest.raises(ClientError) as aws_exc:
            s3_client_aws.head_bucket(Bucket=bucket)
        assert aws_exc.value
        # TODO: seems to be broken/flaky - investigate!
        # with pytest.raises(ClientError) as exc:
        #     s3_client.head_bucket(Bucket=bucket)
        # assert str(exc.value) == str(aws_exc.value)

    # run asynchronously, as apparently this can take some time
    retry(_assert_deleted, retries=5, sleep=5)


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
    queue_arn_aws = sqs_client.get_queue_attributes(
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
    assert ctx.value.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue"

    # send message to AWS, receive locally
    sqs_client_aws.send_message(QueueUrl=queue_url_aws, MessageBody="message 1")
    received = sqs_client.receive_message(QueueUrl=queue_url_aws).get("Messages", [])
    assert len(received) == 1
    assert received[0]["Body"] == "message 1"
    sqs_client.delete_message(QueueUrl=queue_url_aws, ReceiptHandle=received[0]["ReceiptHandle"])

    # send message locally, receive with AWS client
    sqs_client.send_message(QueueUrl=queue_url_aws, MessageBody="message 2")
    received = sqs_client_aws.receive_message(QueueUrl=queue_url_aws).get("Messages", [])
    assert len(received) == 1
    assert received[0]["Body"] == "message 2"

    # assert that using a local queue URL also works for proxying
    queue_arn = sqs_queue_arn(
        queue_name_aws, account_id=TEST_AWS_ACCOUNT_ID, region_name=sqs_client.meta.region_name
    )
    queue_url = sqs_queue_url_for_arn(queue_arn=queue_arn)
    result = sqs_client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    assert result == queue_arn_aws
