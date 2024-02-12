import os

from localstack.config import is_env_not_false
from localstack.constants import INTERNAL_RESOURCE_PATH

# handler path within the internal /_localstack endpoint
HANDLER_PATH_REPLICATE = f"{INTERNAL_RESOURCE_PATH}/aws/replicate"
HANDLER_PATH_PROXIES = f"{INTERNAL_RESOURCE_PATH}/aws/proxies"

# whether to clean up proxy containers (set to "0" to investigate startup issues)
CLEANUP_PROXY_CONTAINERS = is_env_not_false("REPLICATOR_CLEANUP_PROXY_CONTAINERS")

# additional Docker flags to pass to the proxy containers
PROXY_DOCKER_FLAGS = (os.getenv("REPLICATOR_PROXY_DOCKER_FLAGS") or "").strip()

# LS hostname to use for proxy Docker container to register itself at the main container
PROXY_LOCALSTACK_HOST = (os.getenv("REPLICATOR_LOCALSTACK_HOST") or "").strip()
