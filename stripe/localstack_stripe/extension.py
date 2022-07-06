import atexit
import logging

from localstack.extensions.api import Extension, http, services

LOG = logging.getLogger(__name__)


class LocalstripeExtension(Extension):
    name = "localstripe"

    backend_url: str

    def on_platform_start(self):
        # start localstripe when localstack starts
        from . import localstripe

        port = services.external_service_ports.reserve_port()
        self.backend_url = f"http://localhost:{port}"

        localstripe.start(port)
        atexit.register(localstripe.shutdown)

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        # a ProxyHandler forwards all incoming requests to the backend URL
        endpoint = http.ProxyHandler(self.backend_url)

        # add path routes for localhost:4566/stripe
        router.add(
            "/stripe",
            endpoint=endpoint,
        )
        router.add(
            "/stripe/<path:path>",
            endpoint=endpoint,
        )
        # add alternative host routes for stripe.localhost.localstack.cloud:4566
        router.add(
            "/",
            host="stripe.localhost.localstack.cloud:<port>",
            endpoint=endpoint,
        )
        router.add(
            "/<path:path>",
            host="stripe.localhost.localstack.cloud:<port>",
            endpoint=endpoint,
        )
