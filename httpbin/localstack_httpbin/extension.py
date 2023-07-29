import logging
from typing import Optional

from localstack import config, constants
from localstack.config import get_edge_url
from localstack.extensions.api import Extension, http
from localstack.utils.net import get_free_tcp_port

from localstack_httpbin.server import HttpbinServer

LOG = logging.getLogger(__name__)


class HttpbinExtension(Extension):
    name = "httpbin"

    hostname_prefix = "httpbin."

    server: Optional[HttpbinServer]

    def __init__(self):
        self.server = None

    def on_extension_load(self):
        level = logging.DEBUG if config.DEBUG else logging.INFO
        logging.getLogger("localstack_httpbin").setLevel(level=level)
        logging.getLogger("httpbin").setLevel(level=level)

    def on_platform_start(self):
        from localstack_httpbin.vendor.httpbin import core
        core.template['host'] = f"{self.get_public_hostname()}:{config.get_edge_port_http()}"

        self.server = HttpbinServer(get_free_tcp_port())
        LOG.debug("starting httpbin on %s", self.server.url)
        self.server.start()

    def get_public_hostname(self) -> str:
        # FIXME: reconcile with LOCALSTACK_HOST, but this should be accessible via the host
        return  f"{self.hostname_prefix}{constants.LOCALHOST_HOSTNAME}"

    def on_platform_ready(self):
        LOG.info("Serving httpbin on %s", get_edge_url(localstack_hostname=self.get_public_hostname()))

    def on_platform_shutdown(self):
        if self.server:
            self.server.shutdown()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        endpoint = http.ProxyHandler(forward_base_url=self.server.url)

        router.add("/", host=f"{self.hostname_prefix}<host>", endpoint=endpoint)
        router.add("/<path:path>", host=f"{self.hostname_prefix}<host>", endpoint=endpoint)
