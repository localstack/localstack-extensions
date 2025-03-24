import contextlib
from typing import ContextManager

from localstack.services.lambda_.invocation.execution_environment import (
    ExecutionEnvironment,
)
from localstack.services.lambda_.invocation.lambda_models import (
    FunctionVersion,
    InitializationType,
)
from localstack_prometheus.metrics.lambda_ import (
    LOCALSTACK_LAMBDA_ENVIRONMENT_START_TOTAL,
    LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING,
)
from localstack.services.lambda_.invocation.assignment import AssignmentService

from localstack.services.lambda_.invocation.docker_runtime_executor import (
    DockerRuntimeExecutor,
)

def tracked_docker_start(fn, self: DockerRuntimeExecutor, env_vars: dict[str, str]):
    try:
        fn(self, env_vars)
        LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING.inc()
    except Exception:
        raise

def tracked_docker_stop(fn, self: DockerRuntimeExecutor):
    try:
        fn(self)
        LOCALSTACK_LAMBDA_ENVIRONMENT_CONTAINERS_RUNNING.dec()
    except Exception:
        raise

@contextlib.contextmanager
def tracked_get_environment(
    fn,
    self: AssignmentService,
    version_manager_id: str,
    function_version: FunctionVersion,
    provisioning_type: InitializationType,
    ) -> ContextManager[ExecutionEnvironment]:
        has_applicable_env = any(
            env.initialization_type == provisioning_type
            for env in self.environments[version_manager_id].values()
        )
        # If there are no applicable environments, this will be a cold start. 
        # Otherwise, it'll be warm.
        start_type = "warm" if has_applicable_env else "cold"
        LOCALSTACK_LAMBDA_ENVIRONMENT_START_TOTAL.labels(start_type=start_type).inc()
        with fn(self, version_manager_id, function_version, provisioning_type) as execution_env:
            yield execution_env
        
