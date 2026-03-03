import json
import logging

from localstack.http import Request, Response, route

from .. import static
from ..scanner import NoScanError, ScanInProgressError, scanner

LOG = logging.getLogger(__name__)


def _json(data, status=200):
    return Response(
        response=json.dumps(data),
        status=status,
        mimetype="application/json",
    )


class WebApp:
    # Static UI

    @route("/")
    def index(self, request: Request, *args, **kwargs):
        return Response.for_resource(static, "index.html")

    @route("/<path:path>")
    def static_files(self, request: Request, path: str, **kwargs):
        # Route API calls through to their handlers (catch-all guard)
        if path.startswith("api/"):
            return _json({"error": "Not found"}, 404)
        try:
            return Response.for_resource(static, path)
        except Exception:
            return Response.for_resource(static, "index.html")

    # REST API

    @route("/api/status", methods=["GET"])
    def api_status(self, request: Request, **kwargs):
        """Return current scan state and summary."""
        state = scanner.get_state()
        return _json(state.to_dict())

    @route("/api/scans", methods=["POST"])
    def api_start_scan(self, request: Request, **kwargs):
        """Trigger a new scan. Body (optional): {"services": [], "severity": []}"""
        body = {}
        if request.data:
            try:
                body = json.loads(request.data)
            except Exception:
                return _json({"error": "Invalid JSON body"}, 400)

        services = body.get("services") or []
        severity = body.get("severity") or []

        try:
            scan_id = scanner.start_scan(services=services, severity=severity)
            return _json({"scan_id": scan_id, "status": "running"}, 202)
        except ScanInProgressError as e:
            return _json({"error": str(e)}, 409)

    @route("/api/scans/latest", methods=["GET"])
    def api_latest_scan(self, request: Request, **kwargs):
        """Return full findings of the latest scan."""
        state = scanner.get_state()
        if not state.scan_id:
            return _json({"error": "No scan has been run yet"}, 404)

        result = state.to_dict()
        result["findings"] = state.findings
        return _json(result)
