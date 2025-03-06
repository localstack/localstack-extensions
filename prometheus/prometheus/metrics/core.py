from prometheus_client import Counter, Gauge, Histogram

# Core request handling metrics
LOCALSTACK_REQUEST_PROCESSING_SECONDS = Histogram(
    "localstack_request_processing_seconds",
    "Time spent processing LocalStack service requests",
    ["service", "operation", "status", "status_code"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300, 600, 900, 1800, 3600],
)

LOCALSTACK_INFLIGHT_REQUESTS_GAUGE = Gauge(
    "localstack_in_flight_requests",
    "Total number of currently in-flight requests",
    ["service", "operation"],
)
