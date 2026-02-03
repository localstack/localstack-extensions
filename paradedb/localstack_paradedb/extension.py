import os
import socket

from localstack_extensions.utils.docker import ProxiedDockerContainerExtension
from localstack import config

# Environment variables for configuration
ENV_POSTGRES_USER = "PARADEDB_POSTGRES_USER"
ENV_POSTGRES_PASSWORD = "PARADEDB_POSTGRES_PASSWORD"
ENV_POSTGRES_DB = "PARADEDB_POSTGRES_DB"

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
        postgres_port = DEFAULT_POSTGRES_PORT

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
            """Check if ParadeDB port is accepting connections."""
            self._check_tcp_port(self.container_host, self.postgres_port)

        super().__init__(
            image_name=self.DOCKER_IMAGE,
            container_ports=[postgres_port],
            env_vars=env_vars,
            health_check_fn=_tcp_health_check,
            tcp_ports=[postgres_port],  # Enable TCP proxying through gateway
        )

    def tcp_connection_matcher(self, data: bytes) -> bool:
        """
        Identify PostgreSQL/ParadeDB connections by protocol handshake.

        PostgreSQL can start with either:
        1. SSL request: protocol code 80877103 (0x04D2162F)
        2. Startup message: protocol version 3.0 (0x00030000)

        Both use the same format:
        - 4 bytes: message length
        - 4 bytes: protocol version/code
        """
        if len(data) < 8:
            return False

        # Check for SSL request (80877103 = 0x04D2162F)
        if data[4:8] == b"\x04\xd2\x16\x2f":
            return True

        # Check for protocol version 3.0 (0x00030000)
        if data[4:8] == b"\x00\x03\x00\x00":
            return True

        return False

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
        # Clients should connect through the LocalStack gateway
        gateway_host = "paradedb.localhost.localstack.cloud"
        gateway_port = config.LOCALSTACK_HOST.port

        return {
            "host": gateway_host,
            "database": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
            "port": gateway_port,
            "connection_string": (
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{gateway_host}:{gateway_port}/{self.postgres_db}"
            ),
            # Also include container connection details for debugging
            "container_host": self.container_host,
            "container_port": self.postgres_port,
        }
