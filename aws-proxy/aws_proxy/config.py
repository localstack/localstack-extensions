import os

from localstack.config import is_env_not_false
from localstack.constants import INTERNAL_RESOURCE_PATH

# handler path within the internal /_localstack endpoint
HANDLER_PATH_PROXY = f"{INTERNAL_RESOURCE_PATH}/aws/proxy"
HANDLER_PATH_PROXIES = f"{INTERNAL_RESOURCE_PATH}/aws/proxies"

# whether to clean up proxy containers (set to "0" to investigate startup issues)
CLEANUP_PROXY_CONTAINERS = is_env_not_false("PROXY_CLEANUP_CONTAINERS")

# additional Docker flags to pass to the proxy containers
PROXY_DOCKER_FLAGS = (os.getenv("PROXY_DOCKER_FLAGS") or "").strip()

# LS hostname to use for proxy Docker container to register itself at the main container
PROXY_LOCALSTACK_HOST = (os.getenv("PROXY_LOCALSTACK_HOST") or "").strip()
