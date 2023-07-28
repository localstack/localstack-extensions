import logging
import os
from typing import TYPE_CHECKING, Optional

from localstack import config, constants
from localstack.extensions.api import Extension, http
from localstack_ext import config as config_ext

if TYPE_CHECKING:
    # conditional import for type checking during development. the actual import is deferred to plugin loading
    # to help with startup times
    from mailhog.server import MailHogServer

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
    http://mailhog.localhost.localstack.cloud:4566, or http://localhost:4566/mailhog/ (note the trailing
    slash).

    The mailhog SMTP server is configured automatically as ``SMTP_HOST``, so when you use SES, mails get
    automatically delivered to mailhog. Neato burrito.
    """

    name = "localstack-mailhog"

    hostname_prefix = "mailhog."
    """Used for serving through a host rule."""

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
            config_ext.SMTP_HOST = f"localhost:{self.server.smtp_port}"
            os.environ["SMTP_HOST"] = config_ext.SMTP_HOST
            LOG.info("configuring SMTP host to internal mailhog smtp: %s", config_ext.SMTP_HOST)

    def on_platform_ready(self):
        # FIXME: reconcile with LOCALSTACK_HOST. the URL should be reachable from the host (the idea is
        #  that users get a log message they can click on from the terminal)
        hostname_edge_url = f"{constants.LOCALHOST_HOSTNAME}:{config.get_edge_port_http()}"
        url = f"http://{self.hostname_prefix}{hostname_edge_url}"
        LOG.info("serving mailhog extension on host: %s", url)

        # trailing slash is important (see update_gateway_routes comment)
        url = f"{config.get_edge_url()}/{self.server.web_path}/"
        LOG.info("serving mailhog extension on path: %s", url)

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        endpoint = http.ProxyHandler(forward_base_url=self.server.url + "/" + self.server.web_path)

        # hostname aliases
        router.add(
            "/",
            host=f"{self.hostname_prefix}<host>",
            endpoint=endpoint,
        )
        router.add(
            "/<path:path>",
            host=f"{self.hostname_prefix}<host>",
            endpoint=endpoint,
        )

        # serve through the web path. here the werkzeug default functionality of strict slashes would be
        # useful, since the webapp needs to be accessed with a trailing slash (localhost:4566/<webpath>/)
        # otherwise the relative urls (like `images/logo.png`) are resolved as
        # `localhost:4566/images/login.png` which looks like an S3 access and will lead to localstack errors.
        # alas, we disabled this for good reason, so we're stuck with telling the user to add the trailing
        # slash.
        router.add(
            f"/{self.server.web_path}",
            endpoint=endpoint,
        )
        router.add(
            f"/{self.server.web_path}/<path:path>",
            endpoint=endpoint,
        )

    def on_platform_shutdown(self):
        if self.server:
            self.server.shutdown()
