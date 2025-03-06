from prometheus_client import Counter, Gauge, Histogram

# Event processing metrics
LOCALSTACK_PROCESSED_EVENTS_TOTAL = Counter(
    "localstack_processed_events_total",
    "Total number of events processed",
    ["event_source", "event_target", "status"],
)

# Performance and latency metrics
LOCALSTACK_EVENT_PROPAGATION_DELAY_SECONDS = Histogram(
    "localstack_event_propagation_delay_seconds",
    "End-to-end latency between event creation and processing",
    ["event_source", "event_target"],
    buckets=[
        0.001,
        0.005,
        0.01,
        0.05,
        0.1,
        0.5,
        1,
        5,
        10,
        30,
        60,
        300,
        600,
        900,
        1800,
        3600,
    ],
)

LOCALSTACK_EVENT_PROCESSING_DURATION_SECONDS = Histogram(
    "localstack_event_processing_duration_seconds",
    "Time taken to poll, filter, and process event data",
    ["event_source", "event_target"],
    buckets=[
        0.001,
        0.005,
        0.01,
        0.05,
        0.1,
        0.5,
        1,
        5,
        10,
        30,
        60,
        300,
        600,
        900,
        1800,
        3600,
    ],
)

LOCALSTACK_EVENT_THROUGHPUT_GAUGE = Gauge(
    "localstack_event_throughput",
    "Current events processed per second",
    ["event_source", "event_target"],
)

# Error tracking metrics
LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL = Counter(
    "localstack_event_processing_errors_total",
    "Total number of event processing errors",
    ["event_source", "event_target", "error_type"],
)
