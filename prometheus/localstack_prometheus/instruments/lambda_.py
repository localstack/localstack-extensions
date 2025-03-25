import contextlib
from typing import ContextManager

from localstack.services.lambda_.invocation.assignment import AssignmentService
from localstack.services.lambda_.invocation.docker_runtime_executor import (
    DockerRuntimeExecutor,
)
from localstack.services.lambda_.invocation.execution_environment import (
    ExecutionEnvironment,
)
from localstack.services.lambda_.invocation.lambda_models import (
    FunctionVersion,
    InitializationType,
)

from localstack_prometheus.metrics.lambda_ import (
    LOCALSTACK_LAMBDA_ENVIRONMENT_ACTIVE,
    LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING,
    LOCALSTACK_LAMBDA_ENVIRONMENT_START_TOTAL,
)


def count_version_environments(
    assignment_service: AssignmentService, version_manager_id: str, prov_type: InitializationType
):
    """Count environments of a specific provisioning type for a specific version manager"""
    return sum(
        env.initialization_type == prov_type
        for env in assignment_service.environments.get(version_manager_id, {}).values()
    )


def count_service_environments(
    assignment_service: AssignmentService, prov_type: InitializationType
):
    """Count environments of a specific provisioning type across all function versions"""
    return sum(
        count_version_environments(assignment_service, version_manager_id, prov_type)
        for version_manager_id in assignment_service.environments
    )


def init_assignment_service_with_metrics(fn, self: AssignmentService):
    fn(self)
    # Initialise these once, with all subsequent calls being evaluated at collection time.
    LOCALSTACK_LAMBDA_ENVIRONMENT_ACTIVE.labels(
        provisioning_type="provisioned-concurrency"
    ).set_function(lambda: count_service_environments(self, "provisioned-concurrency"))

    LOCALSTACK_LAMBDA_ENVIRONMENT_ACTIVE.labels(provisioning_type="on-demand").set_function(
        lambda: count_service_environments(self, "on-demand")
    )


def tracked_docker_start(fn, self: DockerRuntimeExecutor, env_vars: dict[str, str]):
    fn(self, env_vars)
    LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING.inc()


def tracked_docker_stop(fn, self: DockerRuntimeExecutor):
    fn(self)
    LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING.dec()


@contextlib.contextmanager
def tracked_get_environment(
    fn,
    self: AssignmentService,
    version_manager_id: str,
    function_version: FunctionVersion,
    provisioning_type: InitializationType,
) -> ContextManager[ExecutionEnvironment]:
    applicable_env_count = count_version_environments(self, version_manager_id, provisioning_type)
    # If there are no applicable environments, this will be a cold start.
    # Otherwise, it'll be warm.
    start_type = "warm" if applicable_env_count > 0 else "cold"
    LOCALSTACK_LAMBDA_ENVIRONMENT_START_TOTAL.labels(
        start_type=start_type, provisioning_type=provisioning_type
    ).inc()
    with fn(self, version_manager_id, function_version, provisioning_type) as execution_env:
        yield execution_env
