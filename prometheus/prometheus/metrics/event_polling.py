from prometheus_client import Counter, Gauge, Histogram

# Poll operation tracking
LOCALSTACK_RECORDS_PER_POLL = Histogram(
    "localstack_records_per_poll",
    "Number of records/events received in each poll operation",
    ["event_source", "event_target"],
    buckets=[1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 10_000],
)

LOCALSTACK_POLLED_BATCH_EFFICIENCY_RATIO = Histogram(
    "localstack_batch_efficiency_ratio",
    "Ratio of records received to configured maximum batch size",
    ["event_source", "event_target"],
    buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

LOCALSTACK_POLLER_CALLS_TOTAL = Counter(
    "localstack_poller_calls_total",
    "Total number of poll operations performed",
    ["event_source", "event_target"],
)

LOCALSTACK_POLLER_MISS_TOTAL = Counter(
    "localstack_poller_miss_total",
    "Total number of poll operations that returned no messages",
    ["event_source", "event_target"],
)
