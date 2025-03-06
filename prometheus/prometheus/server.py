import logging

from localstack.extensions.api import http
from localstack.utils.common import TMP_THREADS
from localstack.utils.net import get_free_tcp_port
from localstack.utils.serving import Server
from prometheus_client import REGISTRY, generate_latest, start_http_server

LOG = logging.getLogger(__name__)


class PrometheusServer(Server):
    default_web_path = "_extensions/prometheus"

    def __init__(self, port=None, host="localhost"):
        port = port or get_free_tcp_port()
        super().__init__(port, host)

    def do_run(self):
        self.server, self._thread = start_http_server(self.port, self.host)
        TMP_THREADS.append(self._thread)
        return self.server.serve_forever()

    def do_shutdown(self):
        return self.server.shutdown()

    def metrics(self, *args, **kwargs):
        """Expose the Prometheus metrics"""
        return http.Response(
            response=generate_latest(REGISTRY), status=200, mimetype="text/plain"
        )
