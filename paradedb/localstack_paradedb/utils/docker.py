import re
import socket
import logging
from functools import cache
from typing import Callable

from localstack import config
from localstack.utils.docker_utils import DOCKER_CLIENT
from localstack.extensions.api import Extension
from localstack.utils.container_utils.container_client import PortMappings
from localstack.utils.net import get_addressable_container_host
from localstack.utils.sync import retry

LOG = logging.getLogger(__name__)
logging.getLogger("localstack_paradedb").setLevel(
    logging.DEBUG if config.DEBUG else logging.INFO
)
logging.basicConfig()


class DatabaseDockerContainerExtension(Extension):
    """
    Utility class to create a LocalStack Extension which runs a Docker container
    for a database service that uses a native protocol (e.g., PostgreSQL).

    Unlike HTTP-based services, database connections are made directly to the
    exposed container port rather than through the LocalStack gateway.
    """

    name: str
    """Name of this extension, which must be overridden in a subclass."""
    image_name: str
    """Docker image name"""
    container_ports: list[int]
    """List of network ports of the Docker container spun up by the extension"""
    command: list[str] | None
    """Optional command (and flags) to execute in the container."""
    env_vars: dict[str, str] | None
    """Optional environment variables to pass to the container."""
    health_check_port: int | None
    """Port to use for health check (defaults to first port in container_ports)."""
    health_check_fn: Callable[[], bool] | None
    """Optional custom health check function."""

    def __init__(
        self,
        image_name: str,
        container_ports: list[int],
        command: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        health_check_port: int | None = None,
        health_check_fn: Callable[[], bool] | None = None,
    ):
        self.image_name = image_name
        if not container_ports:
            raise ValueError("container_ports is required")
        self.container_ports = container_ports
        self.container_name = re.sub(r"\W", "-", f"ls-ext-{self.name}")
        self.command = command
        self.env_vars = env_vars
        self.health_check_port = health_check_port or container_ports[0]
        self.health_check_fn = health_check_fn
        self.container_host = get_addressable_container_host()

    def on_extension_load(self):
        LOG.info("Loading ParadeDB extension")

    def on_platform_start(self):
        LOG.info("Starting ParadeDB extension - launching container")
        self.start_container()

    def on_platform_shutdown(self):
        self._remove_container()

    @cache
    def start_container(self) -> None:
        LOG.debug("Starting extension container %s", self.container_name)

        port_mapping = PortMappings()
        for port in self.container_ports:
            port_mapping.add(port)

        kwargs = {}
        if self.command:
            kwargs["command"] = self.command
        if self.env_vars:
            kwargs["env_vars"] = self.env_vars

        try:
            DOCKER_CLIENT.run_container(
                self.image_name,
                detach=True,
                remove=True,
                name=self.container_name,
                ports=port_mapping,
                **kwargs,
            )
        except Exception as e:
            LOG.debug("Failed to start container %s: %s", self.container_name, e)
            raise

        def _check_health():
            if self.health_check_fn:
                assert self.health_check_fn()
            else:
                # Default: TCP socket check
                self._check_tcp_port(self.container_host, self.health_check_port)

        try:
            retry(_check_health, retries=60, sleep=1)
        except Exception as e:
            LOG.info("Failed to connect to container %s: %s", self.container_name, e)
            self._remove_container()
            raise

        LOG.info(
            "Successfully started extension container %s on %s:%s",
            self.container_name,
            self.container_host,
            self.health_check_port,
        )

    def _check_tcp_port(self, host: str, port: int, timeout: float = 2.0) -> None:
        """Check if a TCP port is accepting connections."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            sock.close()
        except (socket.timeout, socket.error) as e:
            raise AssertionError(f"Port {port} not ready: {e}")

    def _remove_container(self):
        LOG.debug("Stopping extension container %s", self.container_name)
        DOCKER_CLIENT.remove_container(
            self.container_name, force=True, check_existence=False
        )

    def get_connection_info(self) -> dict:
        """Return connection information for the database."""
        return {
            "host": self.container_host,
            "ports": {port: port for port in self.container_ports},
        }
