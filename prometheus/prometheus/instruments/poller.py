import logging

from localstack.services.lambda_.event_source_mapping.pollers.poller import (
    EmptyPollResultsException,
    Poller,
)

from prometheus.instruments.util import get_event_target_from_procesor
from prometheus.metrics.event_polling import (
    LOCALSTACK_POLL_EVENTS_DURATION_SECONDS,
    LOCALSTACK_POLL_MISS_TOTAL,
    LOCALSTACK_POLLED_BATCH_SIZE_EFFICIENCY_RATIO,
)
from prometheus.metrics.event_processing import (
    LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL,
)

LOG = logging.getLogger(__name__)


def tracked_poll_events(fn, self: Poller):
    """Track metrics for poll_events operations"""
    event_source = self.event_source()
    event_target = get_event_target_from_procesor(self.processor)

    try:
        with LOCALSTACK_POLL_EVENTS_DURATION_SECONDS.labels(
            event_source=event_source, event_target=event_target
        ).time():
            fn(self)
    except EmptyPollResultsException:
        # set to 0 since it's a batch-miss
        LOCALSTACK_POLLED_BATCH_SIZE_EFFICIENCY_RATIO.labels(
            event_source=event_source, event_target=event_target
        ).observe(0)

        LOCALSTACK_POLL_MISS_TOTAL.labels(
            event_source=event_source, event_target=event_target
        ).inc()

        raise
    except Exception as e:
        error_type = type(e).__name__
        LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL.labels(
            event_source=event_source,
            event_target=event_target,
            error_type=error_type,
        ).inc()
        raise
