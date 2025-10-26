import pytest
from localstack.testing.aws.util import (
    base_aws_client_factory,
    base_aws_session,
    base_testing_aws_client,
)
from localstack.utils.net import wait_for_port_open

from aws_proxy.client.auth_proxy import start_aws_auth_proxy

pytest_plugins = [
    "localstack.testing.pytest.fixtures",
]

# binding proxy to 0.0.0.0 to enable testing in CI
PROXY_BIND_HOST = "0.0.0.0"


@pytest.fixture(scope="session")
def aws_session():
    return base_aws_session()


@pytest.fixture(scope="session")
def aws_client_factory(aws_session):
    return base_aws_client_factory(aws_session)


@pytest.fixture(scope="session")
def aws_client(aws_client_factory):
    return base_testing_aws_client(aws_client_factory)


@pytest.fixture
def start_aws_proxy():
    proxies = []

    def _start(config: dict = None):
        config = config or {}
        config.setdefault("bind_host", PROXY_BIND_HOST)
        proxy = start_aws_auth_proxy(config)
        wait_for_port_open(proxy.port)
        proxies.append(proxy)
        return proxy

    yield _start

    for proxy in proxies:
        proxy.shutdown()
