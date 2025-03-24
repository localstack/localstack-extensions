from prometheus_client import Counter, Gauge, Histogram

# Lambda environment metrics
LOCALSTACK_LAMBDA_ENVIRONMENT_START_TOTAL = Counter(
    "localstack_lambda_environment_start_total",
    "Total count of all Lambda environment starts.",
    ["start_type"],
)

LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING = Gauge(
    "localstack_lambda_environment_containers_running",
    "Number of LocalStack Lambda Docker containers currently running.",
)