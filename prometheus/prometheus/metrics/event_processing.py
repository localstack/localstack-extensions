from prometheus_client import Counter, Gauge, Histogram

# Event processing metrics
LOCALSTACK_PROCESSED_EVENTS_TOTAL = Counter(
    "localstack_processed_events_total",
    "Total number of events processed",
    ["event_source", "event_target", "status"],
)

LOCALSTACK_PROCESS_EVENT_DURATION_SECONDS = Histogram(
    "localstack_process_event_duration_second",
    "Duration to process a polled event from start to completion",
    ["event_source", "event_target"],
    buckets=[0.005, 0.05, 0.5, 5, 30, 60, 300, 900, 3600],
)

LOCALSTACK_IN_FLIGHT_EVENTS_GAUGE = Gauge(
    "localstack_in_flight_events_total",
    "Total number of event batches currently being processed by the target",
    ["event_source", "event_target"],
)

# Performance and latency metrics
LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS = Histogram(
    "localstack_event_propagation_delay_seconds",
    "End-to-end latency between event creation and processing",
    ["event_source", "event_target"],
    buckets=[0.005, 0.05, 0.5, 5, 30, 60, 300, 900, 3600],
)

# Error tracking metrics
LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL = Counter(
    "localstack_event_processing_errors_total",
    "Total number of event processing errors",
    ["event_source", "event_target", "error_type"],
)
