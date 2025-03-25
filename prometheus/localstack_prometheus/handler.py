import logging
import time

from localstack.aws.api import RequestContext
from localstack.aws.chain import Handler, HandlerChain
from localstack.http import Response

from localstack_prometheus.metrics.core import (
    LOCALSTACK_IN_FLIGHT_REQUESTS_GAUGE,
    LOCALSTACK_REQUEST_PROCESSING_DURATION_SECONDS,
)

LOG = logging.getLogger(__name__)


class TimedRequestContext(RequestContext):
    start_time: float | None


class RequestMetricsHandler(Handler):
    """
    Handler that records the start time of incoming requests
    """

    def __call__(self, chain: HandlerChain, context: TimedRequestContext, response: Response):
        # Record the start time
        context.start_time = time.perf_counter()

        # Do not record metrics if no service operation information is found
        if not context.service_operation:
            return

        service, operation = context.service_operation
        LOCALSTACK_IN_FLIGHT_REQUESTS_GAUGE.labels(service=service, operation=operation).inc()


class ResponseMetricsHandler(Handler):
    """
    Handler that records metrics when a response is ready
    """

    def __call__(self, chain: HandlerChain, context: TimedRequestContext, response: Response):
        # Do not record metrics if no service operation information is found
        if not context.service_operation:
            return

        service, operation = context.service_operation
        LOCALSTACK_IN_FLIGHT_REQUESTS_GAUGE.labels(service=service, operation=operation).dec()

        # Do not record if response is None
        if response is None:
            return

        # Do not record if no start_time attribute is found
        if not hasattr(context, "start_time") or context.start_time is None:
            return

        duration = time.perf_counter() - context.start_time

        if (ex := context.service_exception) is not None:
            status = ex.code
        else:
            status = "success"

        status_code = str(response.status_code)

        LOCALSTACK_REQUEST_PROCESSING_DURATION_SECONDS.labels(
            service=service,
            operation=operation,
            status=status,
            status_code=status_code,
        ).observe(duration)
