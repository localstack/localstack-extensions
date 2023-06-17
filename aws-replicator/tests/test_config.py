from aws_replicator.server.aws_request_forwarder import AwsProxyHandler
from aws_replicator.shared.models import ProxyServiceConfig


def test_get_resource_names():
    service_config = ProxyServiceConfig(resources="")
    assert AwsProxyHandler._get_resource_names(service_config) == [".*"]

    service_config = ProxyServiceConfig(resources="foobar")
    assert AwsProxyHandler._get_resource_names(service_config) == ["foobar"]

    service_config = ProxyServiceConfig(resources=["foo", "bar"])
    assert AwsProxyHandler._get_resource_names(service_config) == ["foo", "bar"]
