import time

from localstack.services.lambda_.event_source_mapping.pollers.stream_poller import StreamPoller

from prometheus.instruments.util import get_event_target_from_procesor
from prometheus.metrics.event_polling import (
    LOCALSTACK_POLLED_BATCH_EFFICIENCY_RATIO,
    LOCALSTACK_RECORDS_PER_POLL,
)
from prometheus.metrics.event_processing import (
    LOCALSTACK_EVENT_PROCESSING_DURATION_SECONDS,
)


def tracked_stream_poll_events_from_shard(fn, self: StreamPoller, shard_id, shard_iterator):
    """Stream-specific handler for tracking and processing events from a shard (DynamoDB Streams & Kinesis)"""

    event_source = self.event_source()
    event_target = get_event_target_from_procesor(self.processor)

    original_get_records = self.get_records

    def wrapped_get_records(shard_iterator):
        response = original_get_records(shard_iterator)
        records = response.get("Records", [])
        record_count = len(records)

        if record_count > 0:
            LOCALSTACK_RECORDS_PER_POLL.labels(
                event_source=event_source,
                event_target=event_target,
            ).observe(record_count)

        if (batch_size := self.stream_parameters.get("BatchSize")) > 0:
            LOCALSTACK_POLLED_BATCH_EFFICIENCY_RATIO.labels(
                event_source=event_source, event_target=event_target
            ).observe(record_count / batch_size)

        return response

    self.get_records = wrapped_get_records

    try:
        with LOCALSTACK_EVENT_PROCESSING_DURATION_SECONDS.labels(
            event_source=event_source, event_target=event_target
        ).time():
            return fn(self, shard_id, shard_iterator)
    finally:
        self.get_records = original_get_records
