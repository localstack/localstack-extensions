import logging
import time

from localstack.services.lambda_.event_source_mapping.senders.sender import Sender

from prometheus.metrics.event_processing import (
    LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL,
    LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS,
    LOCALSTACK_IN_FLIGHT_EVENTS_GAUGE,
    LOCALSTACK_PROCESS_EVENT_DURATION_SECONDS,
    LOCALSTACK_PROCESSED_EVENTS_TOTAL,
)

LOG = logging.getLogger(__name__)


def tracked_send_events(fn, self: Sender, events: list[dict] | dict):
    """Track metrics for event sending operations"""
    LOG.debug("Tracking send_events call with %d events", len(events))
    original_events = events.copy()

    if not events:
        # This shouldn't happen but cater for it anyway
        return fn(self, events)

    total_events = len(events)
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

    current_epoch_time = time.perf_counter()
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

    LOCALSTACK_IN_FLIGHT_EVENTS_GAUGE.labels(
        event_source=event_source,
        event_target=event_target,
    ).inc()

    try:
        with LOCALSTACK_PROCESS_EVENT_DURATION_SECONDS.time():
            result = fn(self, original_events)
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
    finally:
        LOCALSTACK_IN_FLIGHT_EVENTS_GAUGE.labels(
            event_source=event_source,
            event_target=event_target,
        ).dec()
