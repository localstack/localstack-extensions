import logging

from localstack.services.lambda_.event_source_mapping.pollers.dynamodb_poller import (
    DynamoDBPoller,
)
from localstack.services.lambda_.event_source_mapping.pollers.kinesis_poller import (
    KinesisPoller,
)
from localstack.services.lambda_.event_source_mapping.pollers.sqs_poller import (
    SqsPoller,
)
from localstack.services.lambda_.event_source_mapping.senders.lambda_sender import (
    LambdaSender,
)
from localstack.utils.patch import Patch, Patches

from localstack_prometheus.instruments.poller import tracked_poll_events
from localstack_prometheus.instruments.sender import tracked_send_events
from localstack_prometheus.instruments.sqs_poller import tracked_sqs_handle_messages
from localstack_prometheus.instruments.stream_poller import tracked_get_records

LOG = logging.getLogger(__name__)


def apply_poller_tracking_patches():
    """Apply all poller metrics tracking patches in one call"""
    patches = Patches(
        [
            # Track entire poll_events function
            Patch.function(target=SqsPoller.poll_events, fn=tracked_poll_events),
            Patch.function(target=KinesisPoller.poll_events, fn=tracked_poll_events),
            Patch.function(target=DynamoDBPoller.poll_events, fn=tracked_poll_events),
            # Track when events get sent to the target lambda
            Patch.function(target=LambdaSender.send_events, fn=tracked_send_events),
            # TODO: Standardise a single abstract method that all Poller subclasses can use to fetch records
            # SQS-specific patches
            Patch.function(
                target=SqsPoller.handle_messages, fn=tracked_sqs_handle_messages
            ),
            # Stream-specific patches
            Patch.function(target=KinesisPoller.get_records, fn=tracked_get_records),
            Patch.function(target=DynamoDBPoller.get_records, fn=tracked_get_records),
            # TODO: How should KafkaPollers be handled?
        ]
    )

    # TODO: Investigate patching subclasses of Poller and Sender to ensure all children have changes
    # since currently, Pipes Senders and Kafka Pollers are unsupported.

    patches.apply()
    LOG.debug("Applied all poller event and latency tracking patches")
    return patches
