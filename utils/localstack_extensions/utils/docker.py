import re
import logging
from functools import cache
from typing import Callable
import requests

from localstack.config import is_env_true
from localstack_extensions.utils.h2_proxy import (
    apply_http2_patches_for_grpc_support,
)
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
from werkzeug.datastructures import Headers

LOG = logging.getLogger(__name__)


class ProxiedDockerContainerExtension(Extension):
    """
    Utility class to create a LocalStack Extension which runs a Docker container that exposes a service
    on one or more ports, with requests being proxied to that container through the LocalStack gateway.

    Requests may potentially use HTTP2 with binary content as the protocol (e.g., gRPC over HTTP2).
    To ensure proper routing of requests, subclasses can define the `http2_ports`.

    For services requiring raw TCP proxying (e.g., native database protocols), use the `tcp_ports`
    parameter to enable transparent TCP forwarding to the container.
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
    Can be either a static hostname, or a pattern like `<regex("(.+\\.)?"):subdomain>myext.<domain>`
    """
    path: str | None
    """Optional path on which to expose the container endpoints."""
    command: list[str] | None
    """Optional command (and flags) to execute in the container."""
    env_vars: dict[str, str] | None
    """Optional environment variables to pass to the container."""
    volumes: list[SimpleVolumeBind] | None
    """Optional volumes to mount into the container."""
    health_check_fn: Callable[[], None] | None
    """
    Optional custom health check function. If not provided, defaults to HTTP GET on main_port.
    The function should raise an exception if the health check fails.
    """
    health_check_retries: int
    """Number of times to retry the health check before giving up."""
    health_check_sleep: float
    """Time in seconds to sleep between health check retries."""

    request_to_port_router: Callable[[Request], int] | None
    """Callable that returns the target port for a given request, for routing purposes"""
    http2_ports: list[int] | None
    """List of ports for which HTTP2 proxy forwarding into the container should be enabled."""
    tcp_ports: list[int] | None
    """
    List of container ports for raw TCP proxying through the gateway.
    Enables transparent TCP forwarding for protocols that don't use HTTP (e.g., native DB protocols).

    When tcp_ports is set, the extension must implement tcp_connection_matcher() to identify
    its traffic by inspecting initial connection bytes.
    """

    tcp_connection_matcher: Callable[[bytes], bool] | None
    """
    Optional function to identify TCP connections belonging to this extension.

    Called with initial connection bytes (up to 512 bytes) to determine if this extension
    should handle the connection. Return True to claim the connection, False otherwise.
    """

    def __init__(
        self,
        image_name: str,
        container_ports: list[int],
        host: str | None = None,
        path: str | None = None,
        command: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        volumes: list[SimpleVolumeBind] | None = None,
        health_check_fn: Callable[[], None] | None = None,
        health_check_retries: int = 60,
        health_check_sleep: float = 1.0,
        request_to_port_router: Callable[[Request], int] | None = None,
        http2_ports: list[int] | None = None,
        tcp_ports: list[int] | None = None,
    ):
        try:
            from localstack.pro.core.utils.container.registry_strategies import CustomizableRegistryStrategy
            self.image_name = CustomizableRegistryStrategy().resolve(image_name)
        except ImportError:
            self.image_name = image_name

        if not container_ports:
            raise ValueError("container_ports is required")
        self.container_ports = container_ports
        self.host = host
        self.path = path
        self.container_name = re.sub(r"\W", "-", f"ls-ext-{self.name}")
        self.command = command
        self.env_vars = env_vars
        self.volumes = volumes
        self.health_check_fn = health_check_fn
        self.health_check_retries = health_check_retries
        self.health_check_sleep = health_check_sleep
        self.request_to_port_router = request_to_port_router
        self.http2_ports = http2_ports
        self.tcp_ports = tcp_ports
        self.main_port = self.container_ports[0]
        self.container_host = get_addressable_container_host()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        if self.path:
            raise NotImplementedError(
                "Path-based routing not yet implemented for this extension"
            )
        # note: for simplicity, starting the external container at startup - could be optimized over time ...
        self.start_container()

        # Determine if HTTP proxy should be set up. Skip it when all container ports are
        # TCP-only and no host restriction is set, since a catch-all HTTP proxy would
        # intercept all requests and break other services.
        uses_http = (
            self.host
            and set(self.container_ports) - set(self.tcp_ports or [])
        )

        if uses_http:
            # add resource for HTTP/1.1 requests
            resource = RuleAdapter(ProxyResource(self.container_host, self.main_port))
            if self.host:
                resource = WithHost(self.host, [resource])
            router.add(resource)

        # apply patches to serve HTTP/2 requests
        for port in self.http2_ports or []:
            apply_http2_patches_for_grpc_support(
                self.container_host, port, self.http2_request_matcher
            )

        # set up raw TCP proxies with protocol detection
        if self.tcp_ports:
            self._setup_tcp_protocol_routing()

    def _setup_tcp_protocol_routing(self):
        """
        Set up TCP routing on the LocalStack gateway for this extension.

        This method patches the gateway's HTTP protocol handler to intercept TCP
        connections and allow this extension to claim them via tcp_connection_matcher().
        This enables multiple TCP protocols to share the main gateway port (4566).

        Uses monkeypatching to intercept dataReceived() before HTTP processing.
        """
        from localstack_extensions.utils.tcp_protocol_router import (
            patch_gateway_for_tcp_routing,
            register_tcp_extension,
        )

        # Get the connection matcher from the extension
        matcher = getattr(self, "tcp_connection_matcher", None)
        if not matcher:
            LOG.warning(
                f"Extension {self.name} has tcp_ports but no tcp_connection_matcher(). "
                "TCP routing will not work without a matcher."
            )
            return

        # Apply gateway patches (only happens once globally)
        patch_gateway_for_tcp_routing()

        # Register this extension for TCP routing
        # Use first port as the default target port
        target_port = self.tcp_ports[0] if self.tcp_ports else self.main_port

        register_tcp_extension(
            extension_name=self.name,
            matcher=matcher,
            backend_host=self.container_host,
            backend_port=target_port,
        )

        LOG.info(
            f"Registered TCP extension {self.name} -> {self.container_host}:{target_port} on gateway"
        )

    def http2_request_matcher(self, headers: Headers) -> bool:
        """
        Define whether an HTTP2 request should be proxied, based on request headers.

        Default implementation returns False (no HTTP2 proxying).
        Override this method in subclasses that need HTTP2 proxying.
        """
        return False

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
        if self.env_vars:
            kwargs["env_vars"] = self.env_vars
        if self.volumes:
            kwargs["volumes"] = self.volumes

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
            # allow running the container in a local server in dev mode
            if not is_env_true(f"{self.name.upper().replace('-', '_')}_DEV_MODE"):
                raise

        # Use custom health check if provided, otherwise default to HTTP GET
        health_check = self.health_check_fn or self._default_health_check

        try:
            retry(
                health_check,
                retries=self.health_check_retries,
                sleep=self.health_check_sleep,
            )
        except Exception as e:
            LOG.info("Failed to connect to container %s: %s", self.container_name, e)
            self._remove_container()
            raise

    def _default_health_check(self) -> None:
        """Default health check: HTTP GET request to the main port."""
        response = requests.get(f"http://{self.container_host}:{self.main_port}/")
        assert response.ok

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
