import logging

from localstack.services.lambda_.event_source_mapping.pollers.dynamodb_poller import DynamoDBPoller
from localstack.services.lambda_.event_source_mapping.pollers.kinesis_poller import KinesisPoller
from localstack.services.lambda_.event_source_mapping.pollers.poller import Poller
from localstack.services.lambda_.event_source_mapping.pollers.sqs_poller import SqsPoller
from localstack.services.lambda_.event_source_mapping.senders.lambda_sender import LambdaSender
from localstack.utils.patch import Patch, Patches

from prometheus.instruments.poller import tracked_poll_events, tracked_send_events
from prometheus.instruments.sqs_poller import tracked_sqs_handle_messages
from prometheus.instruments.stream_poller import tracked_stream_poll_events_from_shard

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
            
            # SQS-specific patches
            Patch.function(target=SqsPoller.handle_messages, fn=tracked_sqs_handle_messages),
            
            # Stream-specific patches
            Patch.function(
                target=KinesisPoller.poll_events_from_shard, fn=tracked_stream_poll_events_from_shard
            ),
            Patch.function(
                target=DynamoDBPoller.poll_events_from_shard, fn=tracked_stream_poll_events_from_shard
            ),
            # TODO: How should KafkaPollers be handled?
        ]
    )

    patches.apply()
    LOG.debug("Applied all poller event and latency tracking patches")
    return patches
