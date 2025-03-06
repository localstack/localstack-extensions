from localstack.services.lambda_.event_source_mapping.pollers.stream_poller import (
    StreamPoller,
)

from prometheus.instruments.util import get_event_target_from_procesor
from prometheus.metrics.event_polling import (
    LOCALSTACK_POLLED_BATCH_SIZE_EFFICIENCY_RATIO,
    LOCALSTACK_POLLED_BATCH_WINDOW_EFFICIENCY_RATIO,
    LOCALSTACK_RECORDS_PER_POLL,
)


def tracked_get_records(fn, self: StreamPoller, shard_iterator: str):
    """Stream-specific handler for retrieving events from a shard iterator (DynamoDB Streams & Kinesis)"""

    event_source = self.event_source()
    event_target = get_event_target_from_procesor(self.processor)

    with LOCALSTACK_POLLED_BATCH_WINDOW_EFFICIENCY_RATIO.time():
        response = fn(shard_iterator)
    records = response.get("Records", [])
    record_count = len(records)

    if record_count > 0:
        LOCALSTACK_RECORDS_PER_POLL.labels(
            event_source=event_source,
            event_target=event_target,
        ).observe(record_count)

    if (batch_size := self.stream_parameters.get("BatchSize")) and batch_size > 0:
        LOCALSTACK_POLLED_BATCH_SIZE_EFFICIENCY_RATIO.labels(
            event_source=event_source, event_target=event_target
        ).observe(record_count / batch_size)

    return response
