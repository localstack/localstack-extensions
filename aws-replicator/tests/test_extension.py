# Note: these tests depend on the extension being installed and actual AWS credentials being configured, such
# that the proxy can be started within the tests. They are designed to be mostly run in CI at this point.
import gzip

import boto3
import pytest
from botocore.exceptions import ClientError
from localstack.aws.connect import connect_to
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
    assert buckets_proxied and buckets_proxied == bucket_aws

    # create bucket
    bucket = s3_create_bucket()
    buckets_proxied = s3_client.list_buckets()["Buckets"]
    bucket_aws = s3_client_aws.list_buckets()["Buckets"]
    assert buckets_proxied == bucket_aws

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
        with pytest.raises(ClientError) as exc:
            s3_client.head_bucket(Bucket=bucket)
        assert str(exc.value) == str(aws_exc.value)

    # run asynchronously, as apparently this can take some time
    retry(_assert_deleted, retries=3, sleep=5)
