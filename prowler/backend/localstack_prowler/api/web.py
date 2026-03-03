import json
import logging

from localstack.http import Request, Response, route

from .. import static
from ..scanner import ScanInProgressError, scanner

LOG = logging.getLogger(__name__)

ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "informational"}
ALLOWED_SERVICES = {
    "accessanalyzer",
    "acm",
    "cloudformation",
    "cloudfront",
    "cloudtrail",
    "cloudwatch",
    "cognito",
    "config",
    "dynamodb",
    "ec2",
    "ecr",
    "ecs",
    "eks",
    "elb",
    "elbv2",
    "emr",
    "eventbridge",
    "glacier",
    "glue",
    "guardduty",
    "iam",
    "kms",
    "lambda",
    "opensearch",
    "organizations",
    "rds",
    "redshift",
    "route53",
    "s3",
    "sagemaker",
    "secretsmanager",
    "ses",
    "shield",
    "sns",
    "sqs",
    "ssm",
    "stepfunctions",
    "sts",
    "transfer",
    "waf",
}


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

        if not isinstance(services, list):
            return _json({"error": "'services' must be a list of strings"}, 400)
        if not isinstance(severity, list):
            return _json({"error": "'severity' must be a list of strings"}, 400)
        if any(not isinstance(item, str) for item in services):
            return _json({"error": "'services' must only contain strings"}, 400)
        if any(not isinstance(item, str) for item in severity):
            return _json({"error": "'severity' must only contain strings"}, 400)

        services = [item.strip().lower() for item in services]
        severity = [item.strip().lower() for item in severity]

        unknown_services = [item for item in services if item not in ALLOWED_SERVICES]
        if unknown_services:
            return _json({"error": f"Unknown services: {', '.join(sorted(set(unknown_services)))}"}, 400)

        unknown_severity = [item for item in severity if item not in ALLOWED_SEVERITIES]
        if unknown_severity:
            return _json({"error": f"Unknown severity: {', '.join(sorted(set(unknown_severity)))}"}, 400)

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
