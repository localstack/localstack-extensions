import re
import sys

import click
import yaml
from localstack.cli import LocalstackCli, LocalstackCliPlugin, console
from localstack.logging.setup import setup_logging
from localstack.utils.files import load_file
from localstack_ext.bootstrap.licensing import is_logged_in

from aws_replicator.shared.models import ProxyConfig, ProxyServiceConfig


class AwsReplicatorPlugin(LocalstackCliPlugin):
    name = "aws-replicator"

    def should_load(self) -> bool:
        return is_logged_in()

    def attach(self, cli: LocalstackCli) -> None:
        group: click.Group = cli.group
        group.add_command(aws)


@click.group(name="aws", help="Utilities for replicating resources from real AWS environments")
def aws():
    pass


@aws.command(name="proxy", help="Start up an authentication proxy against real AWS")
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
def cmd_aws_proxy(services: str, config: str):
    from aws_replicator.client.auth_proxy import start_aws_auth_proxy

    config_json: ProxyConfig = {"services": {}}
    if config:
        config_json = yaml.load(load_file(config), Loader=yaml.SafeLoader)
    if services:
        services = _split_string(services)
        for service in services:
            config_json["services"][service] = ProxyServiceConfig(resources=".*")
    try:
        start_aws_auth_proxy(config_json)
    except Exception as e:
        console.print("Unable to start and register auth proxy: %s" % e)
        sys.exit(1)


@aws.command(name="replicate", help="Replicate the state of an AWS account into LocalStack")
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
