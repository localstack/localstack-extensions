# Note: these tests depend on the extension being installed and actual AWS credentials being configured, such
# that the proxy can be started within the tests. They are designed to be mostly run in CI at this point.

import boto3
import pytest
from botocore.exceptions import ClientError
from localstack.aws.connect import connect_to
from localstack.utils.net import wait_for_port_open

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


def test_s3_requests(start_aws_proxy, s3_create_bucket):
    # start proxy
    config = ProxyConfig(services={"s3": {"resources": ".*"}})
    start_aws_proxy(config)

    # create clients
    s3_client = connect_to().s3
    s3_client_aws = boto3.client("s3")

    # create bucket
    bucket = s3_create_bucket()
    buckets = s3_client.list_buckets()["Buckets"]
    bucket_aws = s3_client_aws.list_buckets()["Buckets"]
    assert buckets == bucket_aws

    # put object
    key = "test-key-with-urlencoded-chars-:+"
    s3_client.put_object(Bucket=bucket, Key=key, Body=b"test 123")

    # get object
    result = s3_client.get_object(Bucket=bucket, Key=key)
    assert result["Body"].read() == b"test 123"

    # delete object
    s3_client.delete_object(Bucket=bucket, Key=key)
    with pytest.raises(ClientError) as exc:
        s3_client.get_object(Bucket=bucket, Key=key)
    exc.match("does not exist")
