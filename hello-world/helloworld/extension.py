import logging
from localstack.extensions.api import Extension


LOG = logging.getLogger(__name__)


class HelloWorldExtension(Extension):
    name = "hello_world_example"

    def on_platform_start(self):
        LOG.info("localstack is starting!")

    def on_platform_ready(self):
        LOG.info("localstack is running!")
