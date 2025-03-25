import logging

from localstack.aws.chain import (
    CompositeExceptionHandler,
    CompositeHandler,
    CompositeResponseHandler,
)
from localstack.extensions.api import Extension, http

from localstack_prometheus.expose import retrieve_metrics
from localstack_prometheus.handler import RequestMetricsHandler, ResponseMetricsHandler
from localstack_prometheus.instruments.patch import (
    apply_lambda_tracking_patches,
    apply_poller_tracking_patches,
)

LOG = logging.getLogger(__name__)


class PrometheusMetricsExtension(Extension):
    name = "prometheus"

    def on_extension_load(self):
        apply_lambda_tracking_patches()
        apply_poller_tracking_patches()
        LOG.debug("PrometheusMetricsExtension: extension is loaded")

    def on_platform_start(self):
        LOG.debug("PrometheusMetricsExtension: localstack is starting")

    def on_platform_ready(self):
        LOG.debug("PrometheusMetricsExtension: localstack is running")

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        router.add("/_extension/metrics", retrieve_metrics)
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
