import logging
import os.path
import threading
import time
from typing import Optional

from localstack import config, constants
from localstack.extensions.api import Extension, aws, http
from localstack.utils.container_utils.container_client import (
    ContainerConfiguration,
    VolumeBind,
    VolumeMappings,
)
from localstack.utils.docker_utils import get_default_volume_dir_mount
from localstack.utils.strings import short_uid

from localai.server import ContainerServer

LOG = logging.getLogger(__name__)


class LocalAIExtension(Extension):
    name = "localstack-localai-extension"

    server: Optional[ContainerServer]
    proxy: Optional[http.ProxyHandler]

    def __init__(self):
        self.server = None
        self.proxy = None

    def on_extension_load(self):
        # TODO: logging should be configured automatically for extensions
        if config.DEBUG:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.getLogger("localai").setLevel(level=level)

    def on_platform_start(self):
        volumes = VolumeMappings()
        # FIXME
        if localstack_volume := get_default_volume_dir_mount():
            models_source = os.path.join(localstack_volume.source, "cache", "localai", "models")
            volumes.append(VolumeBind(models_source, "/build/models"))
        else:
            LOG.warning("no volume mounted, will not be able to store models")

        server = ContainerServer(
            8080,
            ContainerConfiguration(
                image_name="quay.io/go-skynet/local-ai:latest",
                name=f"localstack-localai-{short_uid()}",
                volumes=volumes,
                env_vars={
                    # FIXME: is this a good model to pre-load?
                    #  should we call the extension like the pre-loaded model instead?
                    "PRELOAD_MODELS": '[{"url": "github:go-skynet/model-gallery/gpt4all-j.yaml", "name": "gpt-3.5-turbo"}]',
                },
            ),
        )
        self.server = server
        # FIXME: start can take *very* long, since it may download the localai image (which is several GB),
        #  and then download the pre-trained model, which is another 2GB.
        LOG.info("starting up %s as %s", server.config.image_name, server.config.name)
        server.start()

        def _update_proxy_job():
            # wait until container becomes available and then update the proxy to point to that IP
            i = 1

            while True:
                if self.proxy:
                    if self.server.get_network_ip():
                        LOG.info(
                            "serving LocalAI API on http://localai.%s:%s",
                            constants.LOCALHOST_HOSTNAME,
                            config.get_edge_port_http(),
                        )
                        self.proxy.proxy.forward_base_url = self.server.url
                        break

                time.sleep(i)
                i = i * 2

        threading.Thread(target=_update_proxy_job, daemon=True).start()

    def on_platform_shutdown(self):
        if self.server:
            self.server.shutdown()
            self.server.client.remove_container(self.server.config.name)

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        LOG.info("setting up proxy to %s", self.server.url)
        self.proxy = http.ProxyHandler(forward_base_url=self.server.url)

        # hostname aliases
        router.add(
            "/",
            host="localai.<host>",
            endpoint=self.proxy,
        )
        router.add(
            "/<path:path>",
            host="localai.<host>",
            endpoint=self.proxy,
        )

    def update_request_handlers(self, handlers: aws.CompositeHandler):
        pass

    def update_response_handlers(self, handlers: aws.CompositeResponseHandler):
        pass
