import os
import shlex
import socket

from localstack import config
from localstack.extensions.api import http
from localstack_extensions.utils.docker import ProxiedDockerContainerExtension

# Environment variables for configuration
ENV_IMAGE = "COCKROACHDB_IMAGE"
ENV_FLAGS = "COCKROACHDB_FLAGS"
ENV_USER = "COCKROACHDB_USER"
ENV_DB = "COCKROACHDB_DB"

# Defaults
DEFAULT_IMAGE = "cockroachdb/cockroach:latest"
DEFAULT_USER = "root"
DEFAULT_DB = "defaultdb"
DEFAULT_PORT = 26257


class CockroachDbExtension(ProxiedDockerContainerExtension):
    name = "cockroachdb"

    # Base command args passed to the cockroachdb/cockroach Docker image entrypoint.
    # --store=type=mem,size=1GiB: in-memory store — faster startup, truly ephemeral,
    # avoids filesystem permission issues inside the container.
    # Note: CockroachDB requires at least 640 MiB for in-memory store.
    BASE_COMMAND = ["start-single-node", "--insecure", "--store=type=mem,size=1GiB"]

    def __init__(self):
        image = os.environ.get(ENV_IMAGE, DEFAULT_IMAGE)
        extra_flags = shlex.split((os.environ.get(ENV_FLAGS) or "").strip())

        # Store for connection info (not passed to container — insecure mode
        # auto-creates the root user and defaultdb database)
        self.cockroach_user = os.environ.get(ENV_USER, DEFAULT_USER)
        self.cockroach_db = os.environ.get(ENV_DB, DEFAULT_DB)

        def _health_check():
            self._check_tcp_port(self.container_host, DEFAULT_PORT)

        super().__init__(
            image_name=image,
            container_ports=[DEFAULT_PORT],
            command=self.BASE_COMMAND + extra_flags,
            health_check_fn=_health_check,
            health_check_retries=120,  # 2 minutes — CockroachDB can be slow on first start
            tcp_ports=[DEFAULT_PORT],
        )

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        """
        Override to set up only TCP routing without HTTP proxy.

        CockroachDB uses the native PostgreSQL wire protocol (not HTTP), so we
        only need TCP protocol routing — not HTTP proxying. Adding an HTTP
        proxy without a host restriction would cause all HTTP requests to be
        forwarded to the CockroachDB container, breaking other services.
        """
        self.start_container()

        if self.tcp_ports:
            self._setup_tcp_protocol_routing()

    def tcp_connection_matcher(self, data: bytes) -> bool:
        """
        Identify CockroachDB/PostgreSQL connections by protocol handshake.

        CockroachDB speaks the PostgreSQL wire protocol. Connections start with:
        1. SSL request: protocol code 80877103 (0x04D2162F)
        2. Startup message: protocol version 3.0 (0x00030000)
        """
        if len(data) < 8:
            return False

        # SSL request (80877103 = 0x04D2162F)
        if data[4:8] == b"\x04\xd2\x16\x2f":
            return True

        # Protocol version 3.0 (0x00030000)
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
        """Return connection information for CockroachDB."""
        gateway_host = "cockroachdb.localhost.localstack.cloud"
        gateway_port = config.LOCALSTACK_HOST.port

        return {
            "host": gateway_host,
            "port": gateway_port,
            "user": self.cockroach_user,
            "database": self.cockroach_db,
            "connection_string": (
                f"cockroachdb+psycopg2://{self.cockroach_user}"
                f"@{gateway_host}:{gateway_port}/{self.cockroach_db}"
                f"?sslmode=disable"
            ),
        }
