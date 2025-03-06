import logging

from localstack.services.lambda_.event_source_mapping.pollers.sqs_poller import (
    SqsPoller,
)

from prometheus.instruments.util import get_event_target_from_procesor
from prometheus.metrics.event_polling import (
    LOCALSTACK_POLLED_BATCH_SIZE_EFFICIENCY_RATIO,
    LOCALSTACK_RECORDS_PER_POLL,
)

LOG = logging.getLogger(__name__)


# TODO: Refactor Poller to all use a get_records method
def tracked_sqs_handle_messages(fn, self: SqsPoller, messages: list[dict]):
    """SQS-specific handler for tracking and processing polled messages"""
    event_source = self.event_source()
    event_target = get_event_target_from_procesor(self.processor)

    message_count = len(messages)
    if message_count > 0:
        LOCALSTACK_RECORDS_PER_POLL.labels(
            event_source=event_source,
            event_target=event_target,
        ).observe(message_count)

        if self.batch_size > 0:
            LOCALSTACK_POLLED_BATCH_SIZE_EFFICIENCY_RATIO.labels(
                event_source=event_source, event_target=event_target
            ).observe(message_count / self.batch_size)

    return fn(self, messages)
