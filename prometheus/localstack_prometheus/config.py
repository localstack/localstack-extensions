import os

from localstack.config import is_env_not_false
from localstack.constants import INTERNAL_RESOURCE_PATH

# whether to install the Prometheus JMX agent for exporting JVM metrics.
ENABLE_PROMETHEUS_JMX_EXPORTER = is_env_not_false("ENABLE_PROMETHEUS_JMX_EXPORTER")
