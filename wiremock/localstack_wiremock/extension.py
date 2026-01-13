import os

from localstack.utils.container_utils.container_client import Util
from localstack_wiremock.utils.docker import ProxiedDockerContainerExtension


# Environment variable for WireMock Cloud API token - note: if this value is specified, then the
# `wiremock/wiremock-runner` image is being used, otherwise the `wiremock/wiremock` OSS image.
ENV_WIREMOCK_API_TOKEN = "WIREMOCK_API_TOKEN"
# container port for WireMock endpoint - TODO make configurable over time
PORT = 8080


class WireMockExtension(ProxiedDockerContainerExtension):
    name = "localstack-wiremock"

    HOST = "wiremock.<domain>"
    # name of the OSS Docker image
    DOCKER_IMAGE = "wiremock/wiremock"
    # name of the WireMock Cloud runner Docker image
    DOCKER_IMAGE_RUNNER = "wiremock/wiremock-runner"
    # name of the container
    CONTAINER_NAME = "ls-wiremock"

    def __init__(self):
        env_vars = {}
        image_name = self.DOCKER_IMAGE
        kwargs = {}
        if api_token := os.getenv(ENV_WIREMOCK_API_TOKEN):
            env_vars["WMC_ADMIN_PORT"] = str(PORT)
            # TODO remove?
            # env_vars["WMC_DEFAULT_MODE"] = "record-many"
            env_vars["WMC_API_TOKEN"] = api_token
            env_vars["WMC_RUNNER_ENABLED"] = "true"
            image_name = self.DOCKER_IMAGE_RUNNER
            settings_file = Util.mountable_tmp_file()
            # TODO: set configs in YAML file
            kwargs["volumes"] = ([(settings_file, "/work/.wiremock/wiremock.yaml")],)
        super().__init__(
            image_name=image_name,
            container_ports=[PORT],
            container_name=self.CONTAINER_NAME,
            host=self.HOST,
            **kwargs,
        )
