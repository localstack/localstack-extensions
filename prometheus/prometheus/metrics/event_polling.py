from prometheus_client import Counter, Histogram

# Poll operation tracking
LOCALSTACK_RECORDS_PER_POLL = Histogram(
    "localstack_records_per_poll",
    "Number of records/events received in each poll operation",
    ["event_source", "event_target"],
    buckets=[1, 10, 25, 50, 100, 250, 500, 1000, 10_000],
)

LOCALSTACK_POLL_EVENTS_DURATION_SECONDS = Histogram(
    "localstack_poll_events_duration_seconds",
    "Count of poll events .",
    ["event_source", "event_target"],
    buckets=[0.005, 0.05, 0.5, 5, 30, 60, 300, 900, 3600],
)

LOCALSTACK_POLL_MISS_TOTAL = Counter(
    "localstack_poll_miss_total",
    "Count of poll events with empty responses.",
    ["event_source", "event_target"],
)

LOCALSTACK_POLLED_BATCH_SIZE_EFFICIENCY_RATIO = Histogram(
    "localstack_batch_size_efficiency_ratio",
    "Ratio of records received to configured maximum batch size",
    ["event_source", "event_target"],
    buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

LOCALSTACK_POLLED_BATCH_WINDOW_EFFICIENCY_RATIO = Histogram(
    "localstack_batch_window_efficiency_ratio",
    "Ratio poll duration to configured maximum batch window length",
    ["event_source", "event_target"],
    buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
