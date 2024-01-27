import logging

from localstack import config
from localstack.extensions.api import Extension, http
from rolo.router import RuleAdapter, WithHost
from werkzeug.routing import Submount

LOG = logging.getLogger(__name__)


class LocalstackOpenAIExtension(Extension):
    name = "openai"

    submount = "/_extension/openai"
    subdomain = "openai"

    def on_extension_load(self):
        logging.getLogger("localstack_openai").setLevel(
            logging.DEBUG if config.DEBUG else logging.INFO
        )

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from localstack_openai.mock_openai import Api

        api = RuleAdapter(Api())

        # add path routes for localhost:4566/v1/chat/completion
        router.add(
            [
                Submount(self.submount, [api]),
                WithHost(f"{self.subdomain}.{config.LOCALSTACK_HOST.host}<__host__>", [api]),
            ]
        )

        LOG.info(
            "OpenAI mock available at %s%s", str(config.LOCALSTACK_HOST).rstrip("/"), self.submount
        )
        LOG.info("OpenAI mock available at %s", f"{self.subdomain}.{config.LOCALSTACK_HOST}")
