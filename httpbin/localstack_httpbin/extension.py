import logging
from typing import Optional

from localstack import config
from localstack.extensions.api import Extension, http, aws
from localstack.utils.run import ShellCommandThread

LOG = logging.getLogger(__name__)


class HttpbinExtension(Extension):
    name = "localstack-httpbin-extension"
    process: Optional[ShellCommandThread]
    port: Optional[int]

    def __init__(self):
        self.process = None
        self.port = None

    def on_extension_load(self):
        if config.DEBUG:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.getLogger("localstack_httpbin").setLevel(level=level)
        logging.getLogger("httpbin").setLevel(level=level)

    def on_platform_start(self):
        LOG.info("starting")
        self.port = 5000

        self.process = ShellCommandThread(
            ["/opt/code/localstack/.venv/bin/python", "-m", "httpbin.core"],
            log_listener=self._log_listener
        )
        self.process.start()

    def _log_listener(self, line, **_kwargs):
        LOG.debug(line.rstrip())

    def on_platform_ready(self):
        print("MyExtension: localstack is running")

    def on_platform_shutdown(self):
        if self.process:
            self.process.stop()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        endpoint = http.ProxyHandler(f"http://localhost:{self.port}")

        router.add(
            "/",
            host="httpbin.<host>",
            endpoint=endpoint
        )
        router.add(
            "/<path:path>",
            host="httpbin.<host>",
            endpoint=endpoint
        )

    def update_request_handlers(self, handlers: aws.CompositeHandler):
        pass

    def update_response_handlers(self, handlers: aws.CompositeResponseHandler):
        pass
