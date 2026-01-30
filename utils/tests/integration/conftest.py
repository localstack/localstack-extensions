"""
Integration test fixtures for utils package.

Provides fixtures for running tests against the grpcbin Docker container.
grpcbin is a neutral gRPC test service that supports various RPC types.

Uses ProxiedDockerContainerExtension to manage the grpcbin container,
providing realistic test coverage of the Docker container management infrastructure.
"""

import socket
import pytest

from werkzeug.datastructures import Headers
from localstack_extensions.utils.docker import ProxiedDockerContainerExtension


GRPCBIN_IMAGE = "moul/grpcbin"
GRPCBIN_INSECURE_PORT = 9000  # HTTP/2 without TLS
GRPCBIN_SECURE_PORT = 9001  # HTTP/2 with TLS


class GrpcbinExtension(ProxiedDockerContainerExtension):
    """
    Test extension for grpcbin that uses ProxiedDockerContainerExtension.

    This extension demonstrates using ProxiedDockerContainerExtension for
    a gRPC/HTTP2 service. While grpcbin doesn't use the HTTP gateway routing
    (it's accessed via direct TCP), this tests the Docker container management
    capabilities of ProxiedDockerContainerExtension.
    """

    name = "grpcbin-test"

    def __init__(self):
        def _tcp_health_check():
            """Check if grpcbin insecure port is accepting TCP connections."""
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            try:
                # Use container_host from the parent class
                sock.connect((self.container_host, GRPCBIN_INSECURE_PORT))
                sock.close()
            except (socket.timeout, socket.error) as e:
                raise AssertionError(f"Port {GRPCBIN_INSECURE_PORT} not ready: {e}")

        super().__init__(
            image_name=GRPCBIN_IMAGE,
            container_ports=[GRPCBIN_INSECURE_PORT, GRPCBIN_SECURE_PORT],
            health_check_fn=_tcp_health_check,
        )

    def should_proxy_request(self, headers: Headers) -> bool:
        """
        gRPC services use direct TCP connections, not HTTP gateway routing.
        This method is not used in these tests but is required by the base class.
        """
        return False


@pytest.fixture(scope="session")
def grpcbin_extension():
    """
    Start grpcbin using ProxiedDockerContainerExtension.

    This tests the Docker container management capabilities while providing
    a realistic gRPC/HTTP2 test service for integration tests.
    """
    extension = GrpcbinExtension()

    # Start the container using the extension infrastructure
    extension.start_container()

    yield extension

    # Cleanup
    extension.on_platform_shutdown()


@pytest.fixture
def grpcbin_host(grpcbin_extension):
    """Return the host address for the grpcbin container."""
    return grpcbin_extension.container_host


@pytest.fixture
def grpcbin_insecure_port(grpcbin_extension):
    """Return the insecure (HTTP/2 without TLS) port for grpcbin."""
    return GRPCBIN_INSECURE_PORT


@pytest.fixture
def grpcbin_secure_port(grpcbin_extension):
    """Return the secure (HTTP/2 with TLS) port for grpcbin."""
    return GRPCBIN_SECURE_PORT
