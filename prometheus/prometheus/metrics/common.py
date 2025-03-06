# from prometheus_client import Counter, Gauge, Histogram

# # Base metrics for request handling
# LOCALSTACK_REQUEST_PROCESSING_SECONDS = Histogram(
#     "localstack_handler_request_processing_seconds",
#     "Time spent processing LocalStack service requests",
#     ["service", "operation", "status", "status_code"],
#     buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10],
# )

# LOCALSTACK_INFLIGHT_REQUESTS_GAUGE = Gauge(
#     "localstack_in_flight_requests",
#     "Total number of currently in-flight requests",
#     ["service", "operation"],
# )

# LOCALSTACK_POLLER_MISS_TOTAL = Counter(
#     "localstack_poller_miss_total",
#     "Total number of poll requests that return no messages",
#     ["event_source", "event_target"],
# )

# # Latency and duration metrics with adjusted buckets
# LOCALSTACK_PROPAGATION_DELAY_SECONDS = Histogram(
#     "localstack_propagation_delay_seconds",
#     "End-to-end latency between a record being written to data source until processing",
#     ["event_source", "event_target"],
#     buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300, 600, 900, 1800, 3600],
# )

# LOCALSTACK_PROCESS_EVENTS_DURATION_SECONDS = Histogram(
#     "localstack_process_events_duration_seconds",
#     "Time taken to poll, filter, and process event data",
#     ["event_source", "event_target"],
#     buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300, 600, 900, 1800, 3600],
# )

# LOCALSTACK_PROCESSED_EVENTS_TOTAL = Counter(
#     "localstack_processed_events_total",
#     "Total number of events successfully processed",
#     ["event_source", "event_target", "status"],
# )

# LOCALSTACK_RECORDS_PER_POLL = Histogram(
#     "localstack_records_per_poll",
#     "Number of records/events received in each poll operation",
#     ["event_source", "event_target"],
#     buckets=[1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 10_000],
# )

# LOCALSTACK_POLL_CALLS_TOTAL = Counter(
#     "localstack_poll_calls_total",
#     "Total number of messages polled/ingested.",
#     ["event_source", "event_target"],
# )

# # Ratio of actual batch size to configured BatchSize
# LOCALSTACK_POLLED_BATCH_EFFICIENCY_RATIO = Histogram(
#     "localstack_batch_efficiency_ratio",
#     "Ratio of records requested to a configured maximum (higher is better efficiency)",
#     ["event_source", "event_target"],
#     buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
# )

# LOCALSTACK_EVENT_SIZE_BYTES = Histogram(
#     "localstack_event_size_bytes",
#     "Size of individual events in bytes",
#     ["event_source", "event_target"],
#     buckets=[10, 100, 500, 1000, 5000, 10_000, 50_000, 100_000, 500_000, 1_000_000],
# )

# # Error tracking metrics
# LOCALSTACK_PROCESSING_ERRORS_TOTAL = Counter(
#     "localstack_processing_errors_total",
#     "Total number of event processing errors",
#     ["event_source", "event_target", "error_type"],
# )

# LOCALSTACK_RETRY_ATTEMPTS_TOTAL = Counter(
#     "localstack_retry_attempts_total",
#     "Total number of retry attempts for failed event processing",
#     ["event_source", "event_target"],
# )

# # Throughput tracking for real-time monitoring
# LOCALSTACK_EVENT_THROUGHPUT_GAUGE = Gauge(
#     "localstack_event_throughput",
#     "Current events processed per second",
#     ["event_source", "event_target"],
# )
