import logging
import os
from pathlib import Path
import requests

from localstack import config, constants
from localstack.utils.net import get_addressable_container_host
from localstack_extensions.utils.docker import ProxiedDockerContainerExtension


LOG = logging.getLogger(__name__)

# If set, uses wiremock-runner image; otherwise uses OSS wiremock image
ENV_WIREMOCK_API_TOKEN = "WIREMOCK_API_TOKEN"
# Host path to directory containing .wiremock/ (required for runner mode)
ENV_WIREMOCK_CONFIG_DIR = "WIREMOCK_CONFIG_DIR"

SERVICE_PORT = 8080  # Mock API port
ADMIN_PORT = 9999  # Admin interface port (runner mode)


class WireMockExtension(ProxiedDockerContainerExtension):
    name = "localstack-wiremock"

    HOST = "wiremock.<domain>"
    DOCKER_IMAGE = "wiremock/wiremock"
    DOCKER_IMAGE_RUNNER = "wiremock/wiremock-runner"
    CONTAINER_NAME = "ls-wiremock"

    def __init__(self):
        env_vars = {}
        image_name = self.DOCKER_IMAGE
        volumes = None
        container_ports = [SERVICE_PORT]
        health_check_path = "/__admin/health"
        health_check_retries = 40
        health_check_sleep = 1

        if api_token := os.getenv(ENV_WIREMOCK_API_TOKEN):
            # WireMock Runner mode
            env_vars["WMC_ADMIN_PORT"] = str(ADMIN_PORT)
            env_vars["WMC_API_TOKEN"] = api_token
            env_vars["WMC_RUNNER_ENABLED"] = "true"
            image_name = self.DOCKER_IMAGE_RUNNER
            container_ports = [SERVICE_PORT, ADMIN_PORT]
            health_check_path = "/__/health"
            health_check_retries = 90
            health_check_sleep = 2

            host_config_dir = os.getenv(ENV_WIREMOCK_CONFIG_DIR)

            if not host_config_dir:
                LOG.error("WIREMOCK_CONFIG_DIR is required for WireMock runner mode")
                raise ValueError(
                    "WIREMOCK_CONFIG_DIR must be set to the host path containing .wiremock/"
                )

            host_wiremock_dir = os.path.join(host_config_dir, ".wiremock")

            # Validate config in dev mode
            extension_dir = Path(__file__).parent.parent
            container_wiremock_dir = extension_dir / ".wiremock"
            container_wiremock_yaml = container_wiremock_dir / "wiremock.yaml"

            if container_wiremock_dir.is_dir() and container_wiremock_yaml.is_file():
                LOG.info("WireMock config found at: %s", container_wiremock_dir)
            else:
                LOG.warning("Ensure %s/.wiremock/wiremock.yaml exists", host_config_dir)

            LOG.info("Mounting WireMock config from: %s", host_wiremock_dir)
            volumes = [(host_wiremock_dir, "/work/.wiremock")]

        health_check_port = ADMIN_PORT if api_token else SERVICE_PORT
        self._is_runner_mode = bool(api_token)

        def _health_check():
            """Custom health check for WireMock."""
            container_host = get_addressable_container_host()
            health_url = (
                f"http://{container_host}:{health_check_port}{health_check_path}"
            )
            LOG.debug("Health check: %s", health_url)
            response = requests.get(health_url, timeout=5)
            assert response.ok

        super().__init__(
            image_name=image_name,
            container_ports=container_ports,
            host=self.HOST,
            env_vars=env_vars if env_vars else None,
            volumes=volumes,
            health_check_fn=_health_check,
            health_check_retries=health_check_retries,
            health_check_sleep=health_check_sleep,
        )

    def on_platform_ready(self):
        url = f"http://wiremock.{constants.LOCALHOST_HOSTNAME}:{config.get_edge_port_http()}"
        mode = "Runner" if self._is_runner_mode else "OSS"
        LOG.info("WireMock %s extension ready: %s", mode, url)
