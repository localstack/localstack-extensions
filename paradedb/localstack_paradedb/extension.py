import os
import socket
import logging

from localstack_extensions.utils.docker import ProxiedDockerContainerExtension
from localstack.extensions.api import http
from werkzeug.datastructures import Headers

LOG = logging.getLogger(__name__)

# Environment variables for configuration
ENV_POSTGRES_USER = "PARADEDB_POSTGRES_USER"
ENV_POSTGRES_PASSWORD = "PARADEDB_POSTGRES_PASSWORD"
ENV_POSTGRES_DB = "PARADEDB_POSTGRES_DB"
ENV_POSTGRES_PORT = "PARADEDB_POSTGRES_PORT"

# Default values
DEFAULT_POSTGRES_USER = "myuser"
DEFAULT_POSTGRES_PASSWORD = "mypassword"
DEFAULT_POSTGRES_DB = "mydatabase"
DEFAULT_POSTGRES_PORT = 5432


class ParadeDbExtension(ProxiedDockerContainerExtension):
    name = "paradedb"

    # Name of the Docker image to spin up
    DOCKER_IMAGE = "paradedb/paradedb"

    def __init__(self):
        # Get configuration from environment variables
        postgres_user = os.environ.get(ENV_POSTGRES_USER, DEFAULT_POSTGRES_USER)
        postgres_password = os.environ.get(
            ENV_POSTGRES_PASSWORD, DEFAULT_POSTGRES_PASSWORD
        )
        postgres_db = os.environ.get(ENV_POSTGRES_DB, DEFAULT_POSTGRES_DB)
        postgres_port = int(os.environ.get(ENV_POSTGRES_PORT, DEFAULT_POSTGRES_PORT))

        # Store configuration for connection info
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password
        self.postgres_db = postgres_db
        self.postgres_port = postgres_port

        # Environment variables to pass to the container
        env_vars = {
            "POSTGRES_USER": postgres_user,
            "POSTGRES_PASSWORD": postgres_password,
            "POSTGRES_DB": postgres_db,
        }

        def _tcp_health_check():
            """Check if PostgreSQL port is accepting connections."""
            self._check_tcp_port(self.container_host, self.postgres_port)

        super().__init__(
            image_name=self.DOCKER_IMAGE,
            container_ports=[postgres_port],
            env_vars=env_vars,
            health_check_fn=_tcp_health_check,
        )

    def should_proxy_request(self, headers: Headers) -> bool:
        """
        Define whether a request should be proxied based on request headers.
        For database extensions, this is not used as connections are direct TCP.
        """
        return False

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        """
        Override to start container without setting up HTTP gateway routes.
        Database extensions don't need HTTP routing - clients connect directly via TCP.
        """
        self.start_container()

    def _check_tcp_port(self, host: str, port: int, timeout: float = 2.0) -> None:
        """Check if a TCP port is accepting connections."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            sock.close()
        except (socket.timeout, socket.error) as e:
            raise AssertionError(f"Port {port} not ready: {e}")

    def get_connection_info(self) -> dict:
        """Return connection information for ParadeDB."""
        return {
            "host": self.container_host,
            "database": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
            "port": self.postgres_port,
            "ports": {self.postgres_port: self.postgres_port},
            "connection_string": (
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.container_host}:{self.postgres_port}/{self.postgres_db}"
            ),
        }
