import boto3
from localstack.aws.connect import connect_to

from aws_proxy.shared.models import ProxyConfig
from localstack.utils.strings import short_uid


def test_proxy_create_secret(start_aws_proxy, cleanups):
    # start proxy
    config = ProxyConfig(services={"secretsmanager": {"resources": ".*"}})
    start_aws_proxy(config)

    # create clients
    sm_client = connect_to().secretsmanager
    sm_client_aws = boto3.client("secretsmanager")

    # list buckets to assert that proxy is up and running
    secrets_proxied = sm_client.list_secrets()["SecretList"]
    secrets_aws = sm_client_aws.list_secrets()["SecretList"]
    assert secrets_proxied == secrets_aws

    # create secret in AWS
    secret_name = f"s_{short_uid()}"
    result = sm_client_aws.create_secret(Name=secret_name, SecretString="test")
    secret_id = result["ARN"]
    cleanups.append(lambda: sm_client_aws.delete_secret(SecretId=secret_id))

    # assert that the secret can be retrieved via the proxy
    secret_details = sm_client.describe_secret(SecretId=secret_id)
    secret_details_aws = sm_client.describe_secret(SecretId=secret_id)
    secret_details.pop("ResponseMetadata")
    secret_details_aws.pop("ResponseMetadata")
    assert secret_details == secret_details_aws
