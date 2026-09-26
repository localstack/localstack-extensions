import logging
import os
import shutil
from pathlib import Path

import requests
from localstack import config, constants
from localstack.utils.docker_utils import get_host_path_for_path_in_docker
from localstack.utils.files import mkdir
from localstack.utils.net import get_addressable_container_host
from localstack_extensions.utils.docker import ProxiedDockerContainerExtension

LOG = logging.getLogger(__name__)

# Host path (absolute) or URL of the Mockoon environment data file to serve.
# Also supports `cloud://<environment-id>` references (requires MOCKOON_CLOUD_TOKEN).
ENV_MOCKOON_DATA = "MOCKOON_DATA"
# Token for the Mockoon admin API (default: "test")
ENV_MOCKOON_ADMIN_API_TOKEN = "MOCKOON_ADMIN_API_TOKEN"
# Mockoon Cloud access token, used for `cloud://` data references
ENV_MOCKOON_CLOUD_TOKEN = "MOCKOON_CLOUD_TOKEN"
# Override the Mockoon CLI image (default: mockoon/cli); accepts full ref with optional tag
ENV_MOCKOON_IMAGE = "MOCKOON_IMAGE"

SERVICE_PORT = 3000
DEFAULT_ADMIN_API_TOKEN = "test"
CONTAINER_DATA_FILE = "/data/environment.json"
DEFAULT_ENVIRONMENT_FILE = Path(__file__).parent / "default-environment.json"


class MockoonExtension(ProxiedDockerContainerExtension):
    name = "localstack-mockoon"

    HOST = "mockoon.<domain>"
    DOCKER_IMAGE = "mockoon/cli"

    def __init__(self):
        image_name = os.getenv(ENV_MOCKOON_IMAGE) or self.DOCKER_IMAGE
        env_vars = {
            "MOCKOON_ADMIN_API_TOKEN": os.getenv(ENV_MOCKOON_ADMIN_API_TOKEN)
            or DEFAULT_ADMIN_API_TOKEN
        }
        volumes = None
        command = ["--port", str(SERVICE_PORT), "--hostname", "0.0.0.0"]

        data = os.getenv(ENV_MOCKOON_DATA)
        if data and data.startswith(("http://", "https://", "cloud://")):
            # remote data file - loaded by Mockoon at startup
            command += ["--data", data]
            if cloud_token := os.getenv(ENV_MOCKOON_CLOUD_TOKEN):
                env_vars["MOCKOON_CLOUD_TOKEN"] = cloud_token
        else:
            if data:
                host_data_file = data
            else:
                host_data_file = self._prepare_default_environment()
            LOG.info("Mounting Mockoon data file from: %s", host_data_file)
            volumes = [(host_data_file, CONTAINER_DATA_FILE)]
            # restart the mock server whenever the data file changes on the host
            command += ["--data", CONTAINER_DATA_FILE, "--watch"]

        self._data_source = data or "default environment"

        def _health_check():
            """Health check - any HTTP response indicates that the mock server is up."""
            container_host = get_addressable_container_host()
            requests.get(f"http://{container_host}:{SERVICE_PORT}/", timeout=5)

        super().__init__(
            image_name=image_name,
            container_ports=[SERVICE_PORT],
            host=self.HOST,
            command=command,
            env_vars=env_vars,
            volumes=volumes,
            health_check_fn=_health_check,
            health_check_retries=40,
            health_check_sleep=1,
        )

    @staticmethod
    def _prepare_default_environment() -> str:
        """
        Copy the bundled default environment into the LocalStack volume dir, to make it
        mountable into the Mockoon container. Returns the path of the file on the host.
        """
        target_dir = os.path.join(config.dirs.var_libs, "mockoon")
        mkdir(target_dir)
        target_file = os.path.join(target_dir, "default-environment.json")
        shutil.copyfile(DEFAULT_ENVIRONMENT_FILE, target_file)
        # the Mockoon container runs as a non-root user, hence make the file world-readable
        os.chmod(target_dir, 0o755)
        os.chmod(target_file, 0o644)
        if config.is_in_docker:
            return get_host_path_for_path_in_docker(target_file)
        return target_file

    def on_platform_ready(self):
        url = f"http://mockoon.{constants.LOCALHOST_HOSTNAME}:{config.get_edge_port_http()}"
        LOG.info("Mockoon extension ready (data: %s): %s", self._data_source, url)
