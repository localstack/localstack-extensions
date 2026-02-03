"""
Integration test fixtures for utils package.

Provides fixtures for running tests against the grpcbin Docker container.
grpcbin is a neutral gRPC test service that supports various RPC types.

Uses ProxiedDockerContainerExtension to manage the grpcbin container,
providing realistic test coverage of the Docker container management infrastructure.
"""

import socket
import threading
import time

import pytest
from hyperframe.frame import Frame
from localstack.utils.net import get_free_tcp_port
from rolo import Router
from rolo.gateway import Gateway
from twisted.internet import reactor
from twisted.web import server as twisted_server

from localstack_extensions.utils.docker import ProxiedDockerContainerExtension

GRPCBIN_IMAGE = "moul/grpcbin"
GRPCBIN_INSECURE_PORT = 9000  # HTTP/2 without TLS
GRPCBIN_SECURE_PORT = 9001  # HTTP/2 with TLS

# HTTP/2 protocol constants
HTTP2_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"
SETTINGS_FRAME = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"  # Empty SETTINGS frame


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
            tcp_ports=[GRPCBIN_INSECURE_PORT],  # Enable raw TCP proxying for gRPC/HTTP2
        )

    def tcp_connection_matcher(self, data: bytes) -> bool:
        """Detect HTTP/2 connection preface to route gRPC/HTTP2 traffic."""
        # HTTP/2 connections start with the connection preface
        if len(data) >= len(HTTP2_PREFACE):
            return data.startswith(HTTP2_PREFACE)
        # Also match if we have partial preface data (for early detection)
        return len(data) > 0 and HTTP2_PREFACE.startswith(data)


@pytest.fixture(scope="session")
def grpcbin_extension_server():
    """
    Start grpcbin using ProxiedDockerContainerExtension with a test gateway server.

    This tests the Docker container management and proxy capabilities by:
    1. Starting the grpcbin container via the extension
    2. Setting up a Gateway with the extension's routes and TCP patches
    3. Serving the Gateway on a test port via Twisted
    4. Returning server info for end-to-end testing
    """
    extension = GrpcbinExtension()

    # Create router and update with extension routes
    # This will start the grpcbin container and apply TCP protocol patches
    router = Router()
    extension.update_gateway_routes(router)

    # Create a Gateway with proper TCP support
    # The TCP patches are applied by update_gateway_routes above
    gateway = Gateway(router)

    # Start gateway on a test port using Twisted
    test_port = get_free_tcp_port()
    site = twisted_server.Site(gateway)
    listener = reactor.listenTCP(test_port, site)

    # Run reactor in background thread
    def run_reactor():
        reactor.run(installSignalHandlers=False)

    reactor_thread = threading.Thread(target=run_reactor, daemon=True)
    reactor_thread.start()

    # Wait for reactor to start - not ideal, but should work as a simple solution
    time.sleep(0.5)

    # Return server information for tests
    server_info = {
        "port": test_port,
        "url": f"http://localhost:{test_port}",
        "extension": extension,
        "listener": listener,
    }

    yield server_info

    # Cleanup
    reactor.callFromThread(reactor.stop)
    time.sleep(0.5)
    extension.on_platform_shutdown()


@pytest.fixture(scope="session")
def grpcbin_extension(grpcbin_extension_server):
    """Return the extension instance from the server fixture."""
    return grpcbin_extension_server["extension"]


def parse_server_frames(data: bytes) -> list:
    """Parse HTTP/2 frames from server response data (no preface expected).

    Server responses don't include the HTTP/2 preface - they start with frames directly.
    This function parses raw frame data using hyperframe directly.
    """
    frames = []
    pos = 0
    while pos + 9 <= len(data):  # Frame header is 9 bytes
        try:
            frame, length = Frame.parse_frame_header(memoryview(data[pos : pos + 9]))
            if pos + 9 + length > len(data):
                break  # Incomplete frame
            frame.parse_body(memoryview(data[pos + 9 : pos + 9 + length]))
            frames.append(frame)
            pos += 9 + length
        except Exception:
            break
    return frames
