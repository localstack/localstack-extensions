import logging

from localstack.extensions.api import Extension, http

LOG = logging.getLogger(__name__)


class DiagnosisViewerExtension(Extension):
    name = "diagnosis-viewer"

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from diapretty.server.api import DiagnoseServer
        api = DiagnoseServer()
        router.add("/diapretty", api.serve)
