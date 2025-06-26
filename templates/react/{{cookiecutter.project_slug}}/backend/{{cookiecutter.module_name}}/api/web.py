import logging

from localstack.http import Request, Response, route

from .. import static

LOG = logging.getLogger(__name__)


class WebApp:
    @route("/")
    def index(self, request: Request, *args, **kwargs):
        return Response.for_resource(static, "index.html")

    @route("/<path:path>")
    def index2(self, request: Request, path: str, **kwargs):
        try:
            return Response.for_resource(static, path)
        except Exception:
            LOG.debug(f"File {path} not found, serving index.html")
            return Response.for_resource(static, "index.html")
