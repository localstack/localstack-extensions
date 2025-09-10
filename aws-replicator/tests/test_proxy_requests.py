# Note: these tests depend on the extension being installed and actual AWS credentials being configured, such
# that the proxy can be started within the tests. They are designed to be mostly run in CI at this point.
import gzip
import re
from urllib.parse import urlparse

import boto3
import pytest
from botocore.client import Config
from botocore.exceptions import ClientError
from localstack.aws.connect import connect_to
from localstack.utils.aws.arns import sqs_queue_arn, sqs_queue_url_for_arn
from localstack.utils.aws.resources import create_dynamodb_table
from localstack.utils.net import wait_for_port_open
from localstack.utils.strings import short_uid
from localstack.utils.sync import retry

from aws_replicator.client.auth_proxy import start_aws_auth_proxy
from aws_replicator.shared.models import ProxyConfig

try:
    from localstack.testing.config import TEST_AWS_ACCOUNT_ID
except ImportError:
    # backwards compatibility
    from localstack.constants import TEST_AWS_ACCOUNT_ID

# binding proxy to 0.0.0.0 to enable testing in CI
PROXY_BIND_HOST = "0.0.0.0"


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


@pytest.mark.parametrize(
    "metadata_gzip",
    [
        # True,  TODO re-enable once the logic is fixed
        False
    ],
)
@pytest.mark.parametrize("target_endpoint", ["local_domain", "aws_domain", "default"])
def test_s3_requests(start_aws_proxy, s3_create_bucket, metadata_gzip, target_endpoint):
    # start proxy
    config = ProxyConfig(services={"s3": {"resources": ".*"}}, bind_host=PROXY_BIND_HOST)
    start_aws_proxy(config)

    # create clients
    if target_endpoint == "default":
        s3_client = connect_to().s3
    else:
        s3_client = connect_to(
            endpoint_url="http://s3.localhost.localstack.cloud:4566",
            config=Config(s3={"addressing_style": "virtual"}),
        ).s3

    if target_endpoint == "aws_domain":

        def _add_header(request, **kwargs):
            # instrument boto3 client to add custom `Host` header, mimicking a `*.s3.amazonaws.com` request
            url = urlparse(request.url)
            match = re.match(r"(.+)\.s3\.localhost\.localstack\.cloud", url.netloc)
            if match:
                request.headers.add_header("host", f"{match.group(1)}.s3.us-east-1.amazonaws.com")

        s3_client.meta.events.register_first("before-sign.*.*", _add_header)

    # define S3 client pointing to real AWS
    s3_client_aws = boto3.client("s3")

    # list buckets to assert that proxy is up and running
    buckets_proxied = s3_client.list_buckets()["Buckets"]
    buckets_aws = s3_client_aws.list_buckets()["Buckets"]
    assert buckets_proxied == buckets_aws

    # create bucket
    bucket = s3_create_bucket()
    buckets_proxied = s3_client.list_buckets()["Buckets"]
    buckets_aws = s3_client_aws.list_buckets()["Buckets"]
    assert buckets_proxied and buckets_proxied == buckets_aws

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
        # TODO: for some reason, the proxied result may contain 'DisplayName', whereas result_aws does not
        for res in result_proxied["Contents"] + result_aws["Contents"]:
            res.get("Owner", {}).pop("DisplayName", None)
        assert result_proxied["Contents"] == result_aws["Contents"]

        # list objects v2
        result_aws = s3_client_aws.list_objects_v2(Bucket=bucket, **kwargs)
        result_proxied = s3_client.list_objects_v2(Bucket=bucket, **kwargs)
        # TODO: for some reason, the proxied result may contain 'Owner', whereas result_aws does not
        for res in result_proxied["Contents"]:
            res.pop("Owner", None)
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


def test_s3_list_objects_in_different_folders(start_aws_proxy, s3_create_bucket):
    # start proxy
    config = ProxyConfig(services={"s3": {"resources": ".*"}}, bind_host=PROXY_BIND_HOST)
    start_aws_proxy(config)

    # create clients
    s3_client = connect_to().s3
    s3_client_aws = boto3.client("s3")

    # create bucket
    bucket = s3_create_bucket()
    buckets_proxied = s3_client.list_buckets()["Buckets"]
    buckets_aws = s3_client_aws.list_buckets()["Buckets"]
    assert buckets_proxied and buckets_proxied == buckets_aws

    # create a couple of objects under different paths/folders
    s3_client.put_object(Bucket=bucket, Key="test/foo/bar", Body=b"test")
    s3_client.put_object(Bucket=bucket, Key="test/foo/baz", Body=b"test")
    s3_client.put_object(Bucket=bucket, Key="test/foobar", Body=b"test")

    # list objects for prefix test/
    objects = s3_client_aws.list_objects_v2(Bucket=bucket, Prefix="test/")
    keys_aws = [obj["Key"] for obj in objects["Contents"]]
    objects = s3_client.list_objects_v2(Bucket=bucket, Prefix="test/")
    keys_proxied = [obj["Key"] for obj in objects["Contents"]]
    assert set(keys_proxied) == set(keys_aws)

    # list objects for prefix test/foo/
    objects = s3_client_aws.list_objects_v2(Bucket=bucket, Prefix="test/foo/")
    keys_aws = [obj["Key"] for obj in objects["Contents"]]
    objects = s3_client.list_objects_v2(Bucket=bucket, Prefix="test/foo/")
    keys_proxied = [obj["Key"] for obj in objects["Contents"]]
    assert set(keys_proxied) == set(keys_aws)

    # list objects for prefix test/foo (without trailing slash)
    objects = s3_client_aws.list_objects_v2(Bucket=bucket, Prefix="test/foo")
    keys_aws = [obj["Key"] for obj in objects["Contents"]]
    objects = s3_client.list_objects_v2(Bucket=bucket, Prefix="test/foo")
    keys_proxied = [obj["Key"] for obj in objects["Contents"]]
    assert set(keys_proxied) == set(keys_aws)


def test_sqs_requests(start_aws_proxy, cleanups):
    queue_name_aws = "test-queue-aws"
    queue_name_local = "test-queue-local"

    # start proxy - only forwarding requests for queue name `test-queue-aws`
    config = ProxyConfig(
        services={"sqs": {"resources": f".*:{queue_name_aws}"}}, bind_host=PROXY_BIND_HOST
    )
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


class TestDynamoDBRequests:
    region_name = "us-east-1"

    @pytest.fixture(scope="class")
    def dynamodb_client_aws(self):
        return boto3.client("dynamodb", region_name=self.region_name)

    @pytest.fixture
    def create_dynamodb_table_aws(self, dynamodb_client_aws):
        tables = []

        def factory(**kwargs):
            kwargs["client"] = dynamodb_client_aws
            if "table_name" not in kwargs:
                kwargs["table_name"] = f"test-table-{short_uid()}"
            if "partition_key" not in kwargs:
                kwargs["partition_key"] = "id"

            tables.append(kwargs["table_name"])

            return create_dynamodb_table(**kwargs)

        yield factory

        # cleanup
        for table in tables:
            try:
                dynamodb_client_aws.delete_table(TableName=table)
            except Exception as e:
                print(f"error cleaning up table {table}: {e}", table, e)

    def test_dynamodb_requests_read_only(
        self, start_aws_proxy, create_dynamodb_table_aws, dynamodb_client_aws
    ):
        # create clients
        dynamodb_client = connect_to(region_name=self.region_name).dynamodb

        # start proxy - only forwarding requests for read operations
        config = ProxyConfig(
            services={"dynamodb": {"resources": ".*", "read_only": True}},
            bind_host=PROXY_BIND_HOST,
        )
        start_aws_proxy(config)

        # create table in AWS
        table_name = f"test-table-{short_uid()}"
        create_dynamodb_table_aws(table_name=table_name)
        tables_aws = dynamodb_client_aws.list_tables()["TableNames"]
        assert table_name in tables_aws

        # assert that local call for this table is proxied
        tables_local = dynamodb_client.list_tables()["TableNames"]
        assert table_name in tables_local

        item = {"id": {"S": "123"}, "value": {"S": "foobar"}}
        # put item via AWS client
        dynamodb_client_aws.put_item(TableName=table_name, Item=item)

        # get item via AWS client
        result = dynamodb_client_aws.get_item(TableName=table_name, Key={"id": {"S": "123"}})
        assert result["Item"] == item

        # get item via local client
        result = dynamodb_client.get_item(TableName=table_name, Key={"id": {"S": "123"}})
        assert result["Item"] == item

        # assert that scan operation is working
        result = dynamodb_client.scan(TableName=table_name)
        assert len(result["Items"]) == 1

        # assert that write operation is NOT working - it's sent to localstack, which cannot find the table
        item3 = {"id": {"S": "789"}, "value": {"S": "foobar3"}}
        with pytest.raises(ClientError) as exc:
            dynamodb_client.put_item(TableName=table_name, Item=item3)

        assert exc.match("ResourceNotFoundException")
