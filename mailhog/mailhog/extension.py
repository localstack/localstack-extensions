import os
from typing import TYPE_CHECKING, Optional

from localstack.extensions.api import Extension, http

if TYPE_CHECKING:
    from mailhog.server import MailHogServer

import logging

from localstack import config, constants
from localstack_ext import config as config_ext

LOG = logging.getLogger(__name__)


class MailHogExtension(Extension):
    """
    MailHog extension. Uses environment-based configuration as described here:
    https://github.com/mailhog/MailHog/blob/master/docs/CONFIG.md.

    It exposes three services:
    * The mailhog API
    * The mailhog UI
    * The mailhog SMTP server

    The first two are served through a random port but then routed through the gateway and accessible through
    http://mailhog.localhost.localstack.cloud:4566.

    The mailhog SMTP server is configured automatically as ``SMTP_HOST``, so when you use SES, mails get
    automatically delivered to mailhog. Neato burrito.
    """

    name = "localstack-mailhog-extension"

    server: Optional["MailHogServer"]

    def __init__(self):
        self.server = None

    def on_extension_load(self):
        # TODO: logging should be configured automatically for extensions
        if config.DEBUG:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.getLogger("mailhog").setLevel(level=level)

    def on_platform_start(self):
        from mailhog.server import MailHogServer

        self.server = MailHogServer()
        LOG.info("starting mailhog server")
        self.server.start()

        if not config_ext.SMTP_HOST:
            config_ext.SMTP_HOST = f"localhost:{self.server.get_smtp_port()}"
            os.environ["SMTP_HOST"] = config_ext.SMTP_HOST
            LOG.info("configuring SMTP host to internal mailhog smtp: %s", config_ext.SMTP_HOST)

    def on_platform_ready(self):
        # FIXME: reconcile with LOCALSTACK_HOST (cannot be "localhost:4566" because the UI requires a host
        #  name mapping since it services resources on, e.g., localhost:4566/js, unless `MH_UI_WEB_PATH` is
        #  used). the URL should be reachable from the host (the idea is that users get a log message they
        #  can click on from the terminal)
        url = f"http://mailhog.{constants.LOCALHOST_HOSTNAME}:{config.get_edge_port_http()}"
        LOG.info("serving mailhog extension: %s", url)

    def on_platform_shutdown(self):
        if self.server:
            self.server.shutdown()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        # TODO: consider using `MH_UI_WEB_PATH`
        endpoint = http.ProxyHandler(self.server.url)

        router.add(
            "/",
            host="mailhog.<host>",
            endpoint=endpoint,
        )
        router.add(
            "/<path:path>",
            host="mailhog.<host>",
            endpoint=endpoint,
        )
