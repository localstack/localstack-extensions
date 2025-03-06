import logging

from localstack.aws.chain import (
    CompositeExceptionHandler,
    CompositeHandler,
    CompositeResponseHandler,
)
from localstack.extensions.api import Extension, http

from prometheus.handler import RequestMetricsHandler, ResponseMetricsHandler
from prometheus.instruments.patch import apply_poller_tracking_patches
from prometheus.server import PrometheusServer

LOG = logging.getLogger(__name__)


class PrometheusMetricsExtension(Extension):
    name = "prometheus"
    prometheus_metrics_server: PrometheusServer

    def __init__(self, host="localhost", port=None):
        self.prometheus_metrics_server = PrometheusServer(port, host)

    def on_extension_load(self):
        apply_poller_tracking_patches()
        LOG.debug("PrometheusMetricsExtension: extension is loaded")

    def on_platform_start(self):
        LOG.debug("PrometheusMetricsExtension: localstack is starting")
        self.prometheus_metrics_server.start()

    def on_platform_ready(self):
        LOG.debug("PrometheusMetricsExtension: localstack is running")

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        router.add("/_extension/metrics", self.prometheus_metrics_server.metrics)
        LOG.debug("Added /metrics endpoint for Prometheus metrics")

    def update_request_handlers(self, handlers: CompositeHandler):
        # Prepend the RequestMetricsHandler to handlers ensuring it runs first
        handlers.handlers.insert(0, RequestMetricsHandler())

    def update_response_handlers(self, handlers: CompositeResponseHandler):
        # Insert the ResponseMetricsHandler as the final handler in the chain.
        handlers.handlers.append(ResponseMetricsHandler())

    def update_exception_handlers(self, handlers: CompositeExceptionHandler):
        # TODO
        pass
