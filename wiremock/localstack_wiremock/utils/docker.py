import re
import logging
from functools import cache
from typing import Callable
import requests

from localstack.utils.docker_utils import DOCKER_CLIENT
from localstack.extensions.api import Extension, http
from localstack.http import Request
from localstack.utils.container_utils.container_client import (
    PortMappings,
    SimpleVolumeBind,
)
from localstack.utils.net import get_addressable_container_host
from localstack.utils.sync import retry
from rolo import route
from rolo.proxy import Proxy
from rolo.routing import RuleAdapter, WithHost

LOG = logging.getLogger(__name__)
logging.basicConfig()

# TODO: merge utils with code in TypeDB extension over time ...


class ProxiedDockerContainerExtension(Extension):
    name: str
    """Name of this extension"""
    image_name: str
    """Docker image name"""
    container_name: str | None
    """Name of the Docker container spun up by the extension"""
    container_ports: list[int]
    """List of network ports of the Docker container spun up by the extension"""
    host: str | None
    """
    Optional host on which to expose the container endpoints.
    Can be either a static hostname, or a pattern like `<regex("(.+\.)?"):subdomain>myext.<domain>`
    """
    path: str | None
    """Optional path on which to expose the container endpoints."""
    command: list[str] | None
    """Optional command (and flags) to execute in the container."""

    request_to_port_router: Callable[[Request], int] | None
    """Callable that returns the target port for a given request, for routing purposes"""
    http2_ports: list[int] | None
    """List of ports for which HTTP2 proxy forwarding into the container should be enabled."""

    volumes: list[SimpleVolumeBind] | None = None
    """Optional volumes to mount into the container host."""

    env_vars: dict[str, str] | None = None
    """Optional environment variables to pass to the container."""

    health_check_path: str = "/__admin/health"
    """Health check endpoint path to verify container is ready."""

    health_check_port: int | None = None
    """Port to use for health check. If None, uses the first container port."""

    health_check_retries: int = 40
    """Number of retries for health check."""

    health_check_sleep: float = 1
    """Sleep time between health check retries in seconds."""

    def __init__(
        self,
        image_name: str,
        container_ports: list[int],
        host: str | None = None,
        path: str | None = None,
        container_name: str | None = None,
        command: list[str] | None = None,
        request_to_port_router: Callable[[Request], int] | None = None,
        http2_ports: list[int] | None = None,
        volumes: list[SimpleVolumeBind] | None = None,
        env_vars: dict[str, str] | None = None,
        health_check_path: str = "/__admin/health",
        health_check_port: int | None = None,
        health_check_retries: int = 40,
        health_check_sleep: float = 1,
    ):
        self.image_name = image_name
        self.container_ports = container_ports
        self.host = host
        self.path = path
        self.container_name = container_name
        self.command = command
        self.request_to_port_router = request_to_port_router
        self.http2_ports = http2_ports
        self.volumes = volumes
        self.env_vars = env_vars
        self.health_check_path = health_check_path
        self.health_check_port = health_check_port
        self.health_check_retries = health_check_retries
        self.health_check_sleep = health_check_sleep

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        if self.path:
            raise NotImplementedError(
                "Path-based routing not yet implemented for this extension"
            )
        self.start_container()
        # add resource for HTTP/1.1 requests
        resource = RuleAdapter(ProxyResource(self))
        if self.host:
            resource = WithHost(self.host, [resource])
        router.add(resource)

    def on_platform_shutdown(self):
        self._remove_container()

    def _get_container_name(self) -> str:
        if self.container_name:
            return self.container_name
        name = f"ls-ext-{self.name}"
        name = re.sub(r"\W", "-", name)
        return name

    @cache
    def start_container(self) -> None:
        container_name = self._get_container_name()
        LOG.debug("Starting extension container %s", container_name)

        ports = PortMappings()
        for port in self.container_ports:
            ports.add(port)

        kwargs = {}
        if self.command:
            kwargs["command"] = self.command
        if self.env_vars:
            kwargs["env_vars"] = self.env_vars

        try:
            DOCKER_CLIENT.run_container(
                self.image_name,
                detach=True,
                remove=True,
                name=container_name,
                ports=ports,
                volumes=self.volumes,
                **kwargs,
            )
        except Exception as e:
            LOG.debug("Failed to start container %s: %s", container_name, e)
            raise

        health_port = self.health_check_port or self.container_ports[0]
        container_host = get_addressable_container_host()
        health_url = f"http://{container_host}:{health_port}{self.health_check_path}"

        def _ping_endpoint():
            LOG.debug("Health check: %s", health_url)
            response = requests.get(health_url, timeout=5)
            assert response.ok

        try:
            retry(
                _ping_endpoint,
                retries=self.health_check_retries,
                sleep=self.health_check_sleep,
            )
        except Exception as e:
            LOG.info("Failed to connect to container %s: %s", container_name, e)
            # Log container output for debugging
            try:
                logs = DOCKER_CLIENT.get_container_logs(container_name)
                LOG.info("Container logs for %s:\n%s", container_name, logs)
            except Exception:
                pass
            self._remove_container()
            raise

        LOG.debug("Successfully started extension container %s", container_name)

    def _remove_container(self):
        container_name = self._get_container_name()
        LOG.debug("Stopping extension container %s", container_name)
        DOCKER_CLIENT.remove_container(
            container_name, force=True, check_existence=False
        )


class ProxyResource:
    """
    Simple proxy resource that forwards incoming requests from the
    LocalStack Gateway to the target Docker container.
    """

    extension: ProxiedDockerContainerExtension

    def __init__(self, extension: ProxiedDockerContainerExtension):
        self.extension = extension

    @route("/<path:path>")
    def index(self, request: Request, path: str, *args, **kwargs):
        return self._proxy_request(request, forward_path=f"/{path}")

    def _proxy_request(self, request: Request, forward_path: str, *args, **kwargs):
        self.extension.start_container()

        port = self.extension.container_ports[0]
        container_host = get_addressable_container_host()
        base_url = f"http://{container_host}:{port}"
        proxy = Proxy(forward_base_url=base_url)

        # update content length (may have changed due to content compression)
        if request.method not in ("GET", "OPTIONS"):
            request.headers["Content-Length"] = str(len(request.data))

        # make sure we're forwarding the correct Host header
        request.headers["Host"] = f"localhost:{port}"

        # forward the request to the target
        result = proxy.forward(request, forward_path=forward_path)

        return result
