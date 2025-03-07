from prometheus_client import Gauge, Histogram

# Core request handling metrics
LOCALSTACK_REQUEST_PROCESSING_DURATION_SECONDS = Histogram(
    "localstack_request_processing_duration_seconds",
    "Time spent processing LocalStack service requests",
    ["service", "operation", "status", "status_code"],
    buckets=[0.005, 0.05, 0.5, 5, 30, 60, 300, 900, 3600],
)

LOCALSTACK_INFLIGHT_REQUESTS_GAUGE = Gauge(
    "localstack_in_flight_requests",
    "Total number of currently in-flight requests",
    ["service", "operation"],
)
