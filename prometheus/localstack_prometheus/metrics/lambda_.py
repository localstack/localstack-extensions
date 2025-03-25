from prometheus_client import Counter, Gauge

# Lambda environment metrics
LOCALSTACK_LAMBDA_ENVIRONMENT_START_TOTAL = Counter(
    "localstack_lambda_environment_start_total",
    "Total count of all Lambda environment starts.",
    ["start_type", "provisioning_type"],
)

LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING = Gauge(
    "localstack_lambda_environment_containers_running",
    "Number of LocalStack Lambda Docker containers currently running.",
)

LOCALSTACK_LAMBDA_ENVIRONMENT_ACTIVE = Gauge(
    "localstack_lambda_environments_active",
    "Number of currently active LocalStack Lambda environments.",
    ["provisioning_type"],
)
