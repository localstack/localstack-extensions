import logging

from localstack.extensions.api import Extension, http, aws

from localstack.services.internal import get_internal_apis
from localstack import config

from {{ cookiecutter.module_name }}.backend.web import WebApp

from .util import Routes, Subdomain, Submount

LOG = logging.getLogger(__name__)

class MyExtension(Extension):
    name = "{{ cookiecutter.project_slug }}"

    def on_extension_load(self):
        print("MyExtension: extension is loaded")

    def on_platform_start(self):
        print("MyExtension: localstack is starting")

    def on_platform_ready(self):
        print("MyExtension: localstack is running")

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        LOG.info("Adding route for %s", self.name)
        
        get_internal_apis().add(WebApp())
        from localstack.aws.handlers.cors import ALLOWED_CORS_ORIGINS

        webapp = Routes(WebApp())

        ALLOWED_CORS_ORIGINS.append(f"http://{self.name}.{config.LOCALSTACK_HOST}")
        ALLOWED_CORS_ORIGINS.append(f"https://{self.name}.{config.LOCALSTACK_HOST}")

        router.add(Submount(f"/{self.name}", webapp))
        router.add(Subdomain(f"{self.name}", webapp))

    def update_request_handlers(self, handlers: aws.CompositeHandler):
        pass

    def update_response_handlers(self, handlers: aws.CompositeResponseHandler):
        pass
