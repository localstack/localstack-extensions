"""
Integration test fixtures for utils package.

Provides fixtures for running tests against the grpcbin Docker container.
grpcbin is a neutral gRPC test service that supports various RPC types.
"""

import subprocess
import time
import pytest

from localstack.utils.net import wait_for_port_open


GRPCBIN_IMAGE = "moul/grpcbin"
GRPCBIN_INSECURE_PORT = 9000  # HTTP/2 without TLS
GRPCBIN_SECURE_PORT = 9001  # HTTP/2 with TLS


@pytest.fixture(scope="session")
def grpcbin_container():
    """
    Start a grpcbin Docker container for testing.

    The container exposes:
    - Port 9000: Insecure gRPC (HTTP/2 without TLS)
    - Port 9001: Secure gRPC (HTTP/2 with TLS)

    The container is automatically removed after tests complete.
    """
    container_name = "pytest-grpcbin"

    # Check if Docker is available
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Docker is not available")

    # Remove any existing container with the same name
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        timeout=30,
    )

    # Start the container
    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            container_name,
            "-p",
            f"{GRPCBIN_INSECURE_PORT}:{GRPCBIN_INSECURE_PORT}",
            "-p",
            f"{GRPCBIN_SECURE_PORT}:{GRPCBIN_SECURE_PORT}",
            GRPCBIN_IMAGE,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        pytest.fail(f"Failed to start grpcbin container: {result.stderr}")

    container_id = result.stdout.strip()

    # Wait for the insecure port to be ready
    try:
        wait_for_port_open(GRPCBIN_INSECURE_PORT, retries=60, sleep_time=0.5)
    except Exception:
        # Clean up and fail
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        pytest.fail(f"grpcbin port {GRPCBIN_INSECURE_PORT} did not become available")

    # Give the gRPC server inside the container a moment to fully initialize
    # The port may be open before the HTTP/2 server is ready to process requests
    time.sleep(1.0)

    # Provide connection info to tests
    yield {
        "container_id": container_id,
        "container_name": container_name,
        "host": "localhost",
        "insecure_port": GRPCBIN_INSECURE_PORT,
        "secure_port": GRPCBIN_SECURE_PORT,
    }

    # Cleanup: stop and remove the container
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        timeout=30,
    )


@pytest.fixture
def grpcbin_host(grpcbin_container):
    """Return the host address for the grpcbin container."""
    return grpcbin_container["host"]


@pytest.fixture
def grpcbin_insecure_port(grpcbin_container):
    """Return the insecure (HTTP/2 without TLS) port for grpcbin."""
    return grpcbin_container["insecure_port"]


@pytest.fixture
def grpcbin_secure_port(grpcbin_container):
    """Return the secure (HTTP/2 with TLS) port for grpcbin."""
    return grpcbin_container["secure_port"]
