import atexit
import logging

from localstack.extensions.api import Extension, http, services

LOG = logging.getLogger(__name__)


class LocalstackOpenAIExtension(Extension):
    name = "openai"

    backend_url: str

    def on_platform_start(self):
        # start localstripe when localstack starts
        from . import mock_openai

        port = services.external_service_ports.reserve_port()
        self.backend_url = f"http://localhost:{port}"

        print(f"Starting mock OpenAI service on {self.backend_url}")
        mock_openai.run(port)
        atexit.register(mock_openai.stop)

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        # a ProxyHandler forwards all incoming requests to the backend URL
        endpoint = http.ProxyHandler(self.backend_url)

        # add path routes for localhost:4566/v1/chat/completion
        router.add(
            "/v1/chat/completion",
            endpoint=endpoint,
        )