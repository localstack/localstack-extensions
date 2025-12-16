import re
import logging
from abc import abstractmethod
from functools import cache
from typing import Callable
import requests

from localstack import config
from localstack.config import is_env_true
from localstack_typedb.utils.h2_proxy import (
    apply_http2_patches_for_grpc_support,
    ProxyRequestMatcher,
)
from localstack.utils.docker_utils import DOCKER_CLIENT
from localstack.extensions.api import Extension, http
from localstack.http import Request
from localstack.utils.container_utils.container_client import PortMappings
from localstack.utils.net import get_addressable_container_host
from localstack.utils.sync import retry
from rolo import route
from rolo.proxy import Proxy
from rolo.routing import RuleAdapter, WithHost
from werkzeug.datastructures import Headers

LOG = logging.getLogger(__name__)
logging.getLogger("localstack_typedb").setLevel(
    logging.DEBUG if config.DEBUG else logging.INFO
)
logging.basicConfig()


class ProxiedDockerContainerExtension(Extension):
    """
    Utility class to create a LocalStack Extension which runs a Docker container that exposes a service
    on one or more ports, with requests being proxied to that container through the LocalStack gateway.

    Requests may potentially use HTTP2 with binary content as the protocol (e.g., gRPC over HTTP2).
    To ensure proper routing of requests, subclasses can define the `http2_ports`.
    """

    name: str
    """Name of this extension, which must be overridden in a subclass."""
    image_name: str
    """Docker image name"""
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

    def __init__(
        self,
        image_name: str,
        container_ports: list[int],
        host: str | None = None,
        path: str | None = None,
        command: list[str] | None = None,
        request_to_port_router: Callable[[Request], int] | None = None,
        http2_ports: list[int] | None = None,
    ):
        self.image_name = image_name
        if not container_ports:
            raise ArgumentError("container_ports is required")
        self.container_ports = container_ports
        self.host = host
        self.path = path
        self.container_name = re.sub(
            r"\W", "-", f"ls-ext-{self.name}"
        )
        self.command = command
        self.request_to_port_router = request_to_port_router
        self.http2_ports = http2_ports
        self.main_port = self.container_ports[0]
        self.container_host = get_addressable_container_host()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        if self.path:
            raise NotImplementedError(
                "Path-based routing not yet implemented for this extension"
            )
        # note: for simplicity, starting the external container at startup - could be optimized over time ...
        self.start_container()
        # add resource for HTTP/1.1 requests
        resource = RuleAdapter(ProxyResource(self.container_host, self.main_port))
        if self.host:
            resource = WithHost(self.host, [resource])
        router.add(resource)

        # apply patches to serve HTTP/2 requests
        for port in self.http2_ports or []:
            apply_http2_patches_for_grpc_support(
                self.container_host, port, self.should_proxy_request
            )

    @abstractmethod
    def should_proxy_request(self, headers: Headers) -> bool:
        """Define whether a request should be proxied, based on request headers."""

    def on_platform_shutdown(self):
        self._remove_container()

    @cache
    def start_container(self) -> None:
        LOG.debug("Starting extension container %s", self.container_name)

        port_mapping = PortMappings()
        for port in self.container_ports:
            port_mapping.add(port)

        kwargs = {}
        if self.command:
            kwargs["command"] = self.command

        try:
            DOCKER_CLIENT.run_container(
                self.image_name,
                detach=True,
                remove=True,
                name=self.container_name,
                ports=port_mapping,
                **kwargs,
            )
        except Exception as e:
            LOG.debug("Failed to start container %s: %s", self.container_name, e)
            # allow running TypeDB in a local server in dev mode, if TYPEDB_DEV_MODE is enabled
            if not is_env_true("TYPEDB_DEV_MODE"):
                raise

        def _ping_endpoint():
            # TODO: allow defining a custom healthcheck endpoint ...
            response = requests.get(f"http://{self.container_host}:{self.main_port}/")
            assert response.ok

        try:
            retry(_ping_endpoint, retries=40, sleep=1)
        except Exception as e:
            LOG.info("Failed to connect to container %s: %s", self.container_name, e)
            self._remove_container()
            raise

        LOG.debug("Successfully started extension container %s", self.container_name)

    def _remove_container(self):
        LOG.debug("Stopping extension container %s", self.container_name)
        DOCKER_CLIENT.remove_container(
            self.container_name, force=True, check_existence=False
        )


class ProxyResource:
    """
    Simple proxy resource that forwards incoming requests from the
    LocalStack Gateway to the target Docker container.
    """

    host: str
    port: int

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    @route("/<path:path>")
    def index(self, request: Request, path: str, *args, **kwargs):
        return self._proxy_request(request, forward_path=f"/{path}")

    def _proxy_request(self, request: Request, forward_path: str, *args, **kwargs):
        base_url = f"http://{self.host}:{self.port}"
        proxy = Proxy(forward_base_url=base_url)

        # update content length (may have changed due to content compression)
        if request.method not in ("GET", "OPTIONS"):
            request.headers["Content-Length"] = str(len(request.data))

        # make sure we're forwarding the correct Host header
        request.headers["Host"] = f"localhost:{self.port}"

        # forward the request to the target
        result = proxy.forward(request, forward_path=forward_path)

        return result
