import re
import sys

import click
import yaml
from localstack.cli import LocalstackCli, LocalstackCliPlugin, console
from localstack.logging.setup import setup_logging
from localstack.utils.files import load_file

from aws_replicator.shared.models import ProxyConfig, ProxyServiceConfig

try:
    from localstack.pro.core.bootstrap.auth import get_platform_auth_headers
    from localstack.pro.core.cli.aws import aws
    from localstack.pro.core.config import is_auth_token_configured
except ImportError:
    # Only support anything over version 3.6
    from localstack.pro.core.bootstrap.auth import get_auth_headers as get_platform_auth_headers
    from localstack.pro.core.cli.aws import aws
    from localstack.pro.core.config import is_api_key_configured as is_auth_token_configured


class AwsReplicatorPlugin(LocalstackCliPlugin):
    name = "aws-replicator"

    def should_load(self) -> bool:
        return _is_logged_in() or is_auth_token_configured()

    def attach(self, cli: LocalstackCli) -> None:
        group: click.Group = cli.group
        if not group.get_command(ctx=None, cmd_name="aws"):
            group.add_command(aws)
        aws.add_command(cmd_aws_proxy)
        aws.add_command(cmd_aws_replicate)


# TODO: remove over time as we're phasing out the `login` command
def _is_logged_in() -> bool:
    try:
        get_platform_auth_headers()
        return True
    except Exception:
        return False


@click.command(name="proxy", help="Start up an authentication proxy against real AWS")
@click.option(
    "-s",
    "--services",
    help="Comma-delimited list of services to replicate (e.g., sqs,s3)",
    required=False,
)
@click.option(
    "-c",
    "--config",
    help="Path to config file for detailed proxy configurations",
    required=False,
)
@click.option(
    "--host",
    help="Network bind host to expose the proxy process on (default: 127.0.0.1)",
    required=False,
)
@click.option(
    "--container",
    help="Run the proxy in a container and not on the host",
    required=False,
    is_flag=True,
)
@click.option(
    "-p",
    "--port",
    help="Custom port to run the proxy on (by default a random port is used)",
    required=False,
)
def cmd_aws_proxy(services: str, config: str, container: bool, port: int, host: str):
    from aws_replicator.client.auth_proxy import start_aws_auth_proxy_in_container

    config_json: ProxyConfig = {"services": {}}
    if config:
        config_json = yaml.load(load_file(config), Loader=yaml.SafeLoader)
    if host:
        config_json["bind_host"] = host
    if services:
        services = _split_string(services)
        for service in services:
            config_json["services"][service] = ProxyServiceConfig(resources=".*")
    try:
        if container:
            return start_aws_auth_proxy_in_container(config_json)

        # note: deferring the import here, to avoid import errors in CLI context
        from aws_replicator.client.auth_proxy import start_aws_auth_proxy

        proxy = start_aws_auth_proxy(config_json, port=port)
        proxy.join()
    except Exception as e:
        console.print(f"Unable to start and register auth proxy: {e}")
        sys.exit(1)


@click.command(name="replicate", help="Replicate the state of an AWS account into LocalStack")
@click.option(
    "-s",
    "--services",
    help="Comma-delimited list of services to replicate (e.g., sqs,s3)",
    required=True,
)
def cmd_aws_replicate(services: str):
    from aws_replicator.client.replicate import replicate_state_into_local

    setup_logging()
    services = _split_string(services)
    replicate_state_into_local(services)


def _split_string(string):
    return [s.strip().lower() for s in re.split(r"[\s,]+", string) if s.strip()]
