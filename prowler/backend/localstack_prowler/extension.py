import logging
import typing as t

from localstack.extensions.patterns.webapp import WebAppExtension

from .api.web import WebApp
from .scanner import scanner

LOG = logging.getLogger(__name__)


class ProwlerExtension(WebAppExtension):
    name = "prowler"

    def __init__(self):
        super().__init__(template_package_path=None)

    def on_platform_ready(self):
        LOG.info("Prowler extension ready — pre-pulling Docker image in background")
        import threading
        t = threading.Thread(target=scanner.prefetch_image, daemon=True)
        t.start()

    def collect_routes(self, routes: list[t.Any]):
        routes.append(WebApp())
