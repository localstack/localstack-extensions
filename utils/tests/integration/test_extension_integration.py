"""
Integration tests for ProxiedDockerContainerExtension with grpcbin.

These tests verify that ProxiedDockerContainerExtension properly manages
Docker containers in a realistic scenario, using grpcbin as a test service.
"""

import socket


class TestProxiedDockerContainerExtension:
    """Tests for ProxiedDockerContainerExtension using the GrpcbinExtension."""

    def test_extension_starts_container(self, grpcbin_extension):
        """Test that the extension successfully starts the Docker container."""
        assert grpcbin_extension.container_name == "ls-ext-grpcbin-test"
        assert grpcbin_extension.image_name == "moul/grpcbin"
        assert len(grpcbin_extension.container_ports) == 2

    def test_extension_container_host_is_accessible(self, grpcbin_extension):
        """Test that the container_host is set and accessible."""
        assert grpcbin_extension.container_host is not None
        # container_host should be localhost, localhost.localstack.cloud, or a docker bridge IP
        assert grpcbin_extension.container_host in (
            "localhost",
            "127.0.0.1",
            "localhost.localstack.cloud",
        ) or grpcbin_extension.container_host.startswith("172.")

    def test_extension_ports_are_reachable(self, grpcbin_host, grpcbin_insecure_port):
        """Test that the extension's ports are reachable via TCP."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        try:
            sock.connect((grpcbin_host, grpcbin_insecure_port))
            sock.close()
            # Connection successful
        except (socket.timeout, socket.error) as e:
            raise AssertionError(f"Could not connect to grpcbin port: {e}")

    def test_extension_implements_required_methods(self, grpcbin_extension):
        """Test that the extension properly implements the required abstract methods."""
        from werkzeug.datastructures import Headers

        # http2_request_matcher should be callable
        result = grpcbin_extension.http2_request_matcher(Headers())
        assert result is False, "gRPC services should not proxy through HTTP gateway"

    def test_multiple_ports_configured(self, grpcbin_extension):
        """Test that the extension properly handles multiple ports."""
        assert 9000 in grpcbin_extension.container_ports  # insecure port
        assert 9001 in grpcbin_extension.container_ports  # secure port
