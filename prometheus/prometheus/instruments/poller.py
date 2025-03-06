import logging
import time

from localstack.services.lambda_.event_source_mapping.pollers.poller import (
    EmptyPollResultsException,
    Poller,
)
from localstack.services.lambda_.event_source_mapping.senders.sender import Sender

from prometheus.instruments.util import get_event_target_from_procesor
from prometheus.metrics.event_polling import (
    LOCALSTACK_POLLED_BATCH_EFFICIENCY_RATIO,
    LOCALSTACK_POLLER_MISS_TOTAL,
)
from prometheus.metrics.event_processing import (
    LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL,
    LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS,
    LOCALSTACK_PROCESSED_EVENTS_TOTAL,
)

LOG = logging.getLogger(__name__)


def tracked_poll_events(fn, self: Poller):
    """Track metrics for poll_events operations"""
    event_source = self.event_source()
    event_target = get_event_target_from_procesor(self.processor)

    try:
        with LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS.labels(
            event_source=event_source,
            event_target=event_target,
        ).time():
            fn(self)
    except EmptyPollResultsException:
        LOCALSTACK_POLLER_MISS_TOTAL.labels(
            event_source=event_source,
            event_target=event_target,
        ).inc()

        # set to 0 since it's a batch-miss
        LOCALSTACK_POLLED_BATCH_EFFICIENCY_RATIO.labels(
            event_source=event_source, event_target=event_target
        ).observe(0)

        raise
    except Exception as e:
        error_type = type(e).__name__
        LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL.labels(
            event_source=event_source,
            event_target=event_target,
            error_type=error_type,
        ).inc()
        raise


def tracked_send_events(fn, self: Sender, events: list[dict] | dict):
    """Track metrics for event sending operations"""
    LOG.debug("Tracking send_events call with %d events", len(events))
    if not events:
        # This shouldn't happen but cater for it anyway
        return fn(self, events)

    total_events = len(events)
    current_epoch_time = time.time()

    event_target = self.event_target()

    event_source = ""
    if isinstance(events, dict) and (es := events.get("eventSource")):
        event_source = es
    elif isinstance(events, list) and (es := events[0].get("eventSource")):
        event_source = es

    # HACK: Workaround for Kafka since events are a dict
    if event_source in {"aws:kafka", "SelfManagedKafka"} and isinstance(events, dict):
        # Need to flatten 2d array since records are split by topic-partition key
        events = sum(events.get("records", []), [])

    for event in events:
        if not isinstance(event, dict):
            continue

        if dynamodb := event.get("dynamodb", {}):
            if creation_time := dynamodb.get("ApproximateCreationDateTime"):
                delay = current_epoch_time - float(creation_time)
                LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS.labels(
                    event_source=event_source or "aws:dynamodb",
                    event_target=event_target,
                ).observe(delay)

        elif kinesis := event.get("kinesis", {}):
            if arrival_time := kinesis.get("approximateArrivalTimestamp"):
                delay = current_epoch_time - float(arrival_time)
                LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS.labels(
                    event_source=event_source or "aws:kinesis",
                    event_target=event_target,
                ).observe(delay)

        elif sqs_attributes := event.get("attributes", {}):
            if sent_timestamp := sqs_attributes.get("SentTimestamp"):
                delay = current_epoch_time - (float(sent_timestamp) / 1000.0)
                LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS.labels(
                    event_source=event_source or "aws:sqs", event_target=event_target
                ).observe(delay)
        elif event_source in {"aws:kafka", "SelfManagedKafka"}:
            if sent_timestamp := event.get("timestamp"):
                delay = current_epoch_time - (float(sent_timestamp) / 1000.0)
                LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS.labels(
                    event_source=event_source, event_target=event_target
                ).observe(delay)

    LOCALSTACK_PROCESSED_EVENTS_TOTAL.labels(
        event_source=event_source, event_target=event_target, status="processing"
    ).inc(total_events)

    try:
        result = fn(self, events)
        LOCALSTACK_PROCESSED_EVENTS_TOTAL.labels(
            event_source=event_source, event_target=event_target, status="success"
        ).inc(total_events)

        return result

    except Exception as e:
        error_type = type(e).__name__
        LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL.labels(
            event_source=event_source, event_target=event_target, error_type=error_type
        ).inc()

        LOCALSTACK_PROCESSED_EVENTS_TOTAL.labels(
            event_source=event_source, event_target=event_target, status="error"
        ).inc(total_events)
        raise
