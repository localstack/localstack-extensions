from prometheus_client import Counter, Histogram

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
    buckets=[0.005, 0.05, 0.5, 5, 30, 60, 300, 900, 3600],
)

# Error tracking metrics
LOCALSTACK_EVENT_PROCESSING_ERRORS_TOTAL = Counter(
    "localstack_event_processing_errors_total",
    "Total number of event processing errors",
    ["event_source", "event_target", "error_type"],
)
