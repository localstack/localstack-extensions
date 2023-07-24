import pytest
from localstack.testing.aws.util import primary_testing_aws_client, base_aws_client_factory, base_aws_session

pytest_plugins = [
    "localstack.testing.pytest.fixtures",
]


@pytest.fixture(scope="session")
def aws_session():
    return base_aws_session()


@pytest.fixture(scope="session")
def aws_client_factory(aws_session):
    return base_aws_client_factory(aws_session)


@pytest.fixture(scope="session")
def aws_client(aws_client_factory):
    return primary_testing_aws_client(aws_client_factory)
