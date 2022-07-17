import sys
import click
from localstack.cli import LocalstackCliPlugin, LocalstackCli
from localstack_ext.bootstrap.licensing import is_logged_in
from localstack.cli import console
from localstack.logging.setup import setup_logging


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
def cmd_aws_proxy():
    from aws_replicator.auth_proxy import start_aws_auth_proxy

    try:
        start_aws_auth_proxy()
    except Exception as e:
        console.print("Unable to start and register auth proxy: %s" % e)
        sys.exit(1)


@aws.command(name="replicate", help="Replicate the state of an AWS account into LocalStack")
def cmd_aws_replicate():
    from aws_replicator.replicate import replicate_state_into_local

    setup_logging()
    replicate_state_into_local()
