from localstack.http import route, Request, Response

from ..frontend import build

class WebApp:
    @route("/")
    def index(self, request: Request, *args, **kwargs):
        return Response.for_resource(build, "index.html")
    
    @route("/<path:path>")
    def index2(self, request: Request, path: str, **kwargs):
        return Response.for_resource(build, path)
