import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

LOG = logging.getLogger(__name__)

PROWLER_IMAGE = os.environ.get("PROWLER_DOCKER_IMAGE", "prowlercloud/prowler:latest")


def _resolve_localstack_endpoint() -> str:
    if endpoint := os.environ.get("PROWLER_LOCALSTACK_ENDPOINT"):
        return endpoint
    return "http://host.docker.internal:4566"


def _resolve_host_path(container_path: str) -> str:
    """
    Resolve the Docker-host-side path for a path inside this container,
    by reading /proc/self/mountinfo.  Falls back to the container path itself
    (which works when running directly on the host, not inside Docker).
    """
    try:
        with open("/proc/self/mountinfo") as fh:
            for line in fh:
                parts = line.split()
                # fields: id parent_id major:minor root mount_point options ... - fstype source mount_opts
                # We look for lines where mount_point matches our container_path prefix
                if len(parts) < 5:
                    continue
                mount_point = parts[4]
                if container_path.startswith(mount_point) and mount_point != "/":
                    # Find the "source" field (after the " - " separator)
                    sep_idx = parts.index("-") if "-" in parts else -1
                    if sep_idx > 0 and sep_idx + 2 < len(parts):
                        fs_source = parts[sep_idx + 2]  # e.g. /run/host_mark/Users
                        root = parts[3]  # e.g. /harshcasper/Library/...
                        # Reconstruct host path: fs_source + root + (suffix past mount_point)
                        suffix = container_path[len(mount_point):]
                        host_path = fs_source + root + suffix
                        # Normalise double slashes
                        host_path = os.path.normpath(host_path)
                        if os.path.exists(os.path.dirname(host_path)) or os.path.exists(host_path):
                            return host_path
                        # Also try with /Users prefix stripped from fs_source on macOS
                        alt = "/Users" + root + suffix
                        alt = os.path.normpath(alt)
                        return alt
    except Exception:
        pass
    return container_path


class ScanInProgressError(Exception):
    pass


@dataclass(frozen=True)
class ScanOutputDirs:
    container: str
    host: str


@dataclass
class ScanState:
    scan_id: str
    status: str  # idle | running | completed | failed
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    services: list = field(default_factory=list)
    severity: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    error: Optional[str] = None

    def summary(self) -> dict:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0, "pass": 0, "fail": 0, "total": 0}
        for f in self.findings:
            status = (f.get("status") or "").upper()
            sev = (f.get("severity") or "").lower()
            if status == "PASS":
                counts["pass"] += 1
            elif status == "FAIL":
                counts["fail"] += 1
            if sev in counts:
                counts[sev] += 1
            counts["total"] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "services": self.services,
            "severity": self.severity,
            "summary": self.summary(),
            "error": self.error,
        }


def _prepare_scan_output_dirs(scan_id: str) -> ScanOutputDirs:
    # Use /var/lib/localstack as the base — it's a mounted volume shared with the host.
    container_outdir = f"/var/lib/localstack/prowler-{scan_id[:8]}"
    os.makedirs(container_outdir, exist_ok=True)
    host_outdir = _resolve_host_path(container_outdir)
    LOG.info("Prowler output: container=%s  host=%s", container_outdir, host_outdir)
    return ScanOutputDirs(container=container_outdir, host=host_outdir)


def _build_scan_command(services: list, severity: list) -> list[str]:
    cmd = [
        "aws",
        "--output-formats", "json-ocsf",
        "--no-banner",
        "--ignore-exit-code-3",
        "--region", "us-east-1",
        "--output-directory", "/tmp/prowler-output",
    ]
    if services:
        cmd += ["--service"] + services
    if severity:
        cmd += ["--severity"] + severity
    return cmd


def _build_scan_environment(endpoint: str) -> dict[str, str]:
    return {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_SECURITY_TOKEN": "test",
        "AWS_SESSION_TOKEN": "test",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ENDPOINT_URL": endpoint,
    }


def _load_ocsf_findings(container_outdir: str, scan_id: str) -> list[dict]:
    import glob as _glob
    import json

    ocsf_files = _glob.glob(f"{container_outdir}/*.ocsf.json")
    LOG.info("OCSF files found at %s: %s", container_outdir, ocsf_files)
    if not ocsf_files:
        LOG.warning("No JSON-OCSF output found for scan %s in %s", scan_id, container_outdir)
        return []

    with open(ocsf_files[0]) as fh:
        raw = json.load(fh)
        findings = raw if isinstance(raw, list) else []

    LOG.info("Parsed %d findings from scan %s", len(findings), scan_id)
    return findings


class ProwlerScanner:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: ScanState = ScanState(scan_id="", status="idle")
        self._client = None

    def _docker(self):
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    def prefetch_image(self):
        try:
            LOG.info("Pre-pulling Prowler image: %s", PROWLER_IMAGE)
            self._docker().images.pull(PROWLER_IMAGE)
            LOG.info("Prowler image ready: %s", PROWLER_IMAGE)
        except Exception as e:
            LOG.warning("Failed to pre-pull Prowler image %s: %s", PROWLER_IMAGE, e)

    def get_state(self) -> ScanState:
        with self._lock:
            return self._state

    def start_scan(self, services: list = None, severity: list = None) -> str:
        with self._lock:
            if self._state.status == "running":
                raise ScanInProgressError("A scan is already in progress")
            scan_id = str(uuid.uuid4())
            self._state = ScanState(
                scan_id=scan_id,
                status="running",
                started_at=datetime.now(timezone.utc),
                services=services or [],
                severity=severity or [],
            )

        thread = threading.Thread(target=self._run, args=(scan_id, services or [], severity or []), daemon=True)
        thread.start()
        return scan_id

    def _run(self, scan_id: str, services: list, severity: list):
        outdirs = _prepare_scan_output_dirs(scan_id)

        try:
            endpoint = _resolve_localstack_endpoint()
            LOG.info("Starting Prowler scan %s → %s", scan_id, endpoint)
            cmd = _build_scan_command(services, severity)
            env = _build_scan_environment(endpoint)

            self._docker().containers.run(
                PROWLER_IMAGE,
                command=cmd,
                environment=env,
                volumes={outdirs.host: {"bind": "/tmp/prowler-output", "mode": "rw"}},
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
            )

            findings = _load_ocsf_findings(outdirs.container, scan_id)
            normalised = [_normalise_finding(f) for f in findings]

            with self._lock:
                if self._state.scan_id == scan_id:
                    self._state.status = "completed"
                    self._state.finished_at = datetime.now(timezone.utc)
                    self._state.findings = normalised

        except Exception as e:
            LOG.exception("Scan %s failed: %s", scan_id, e)
            with self._lock:
                if self._state.scan_id == scan_id:
                    self._state.status = "failed"
                    self._state.finished_at = datetime.now(timezone.utc)
                    self._state.error = str(e)


def _normalise_finding(raw: dict) -> dict:
    """Flatten relevant OCSF fields into a simple dict for the API/UI."""
    resources = raw.get("resources") or []
    resource = resources[0] if resources else {}
    resource_uid = resource.get("uid") or resource.get("name", "")

    finding = raw.get("finding_info") or {}
    # Prowler 5.x OCSF: severity is already a human-readable string ("Critical", "High", etc.)
    severity = (raw.get("severity") or "informational").lower()

    # Extract AWS service from the check_id (format: prowler-aws-<service>_<check>-...)
    check_uid = finding.get("uid", "")
    service = ""
    if check_uid.startswith("prowler-aws-"):
        remainder = check_uid[len("prowler-aws-"):]
        service = remainder.split("_")[0]

    cloud = raw.get("cloud") or {}
    region = cloud.get("region") or (resource.get("region", ""))

    return {
        "check_id": check_uid.split("-")[2] if check_uid.count("-") >= 2 else check_uid,
        "check_title": finding.get("title", ""),
        "service": service,
        "severity": severity,
        "status": raw.get("status_code", ""),
        "status_extended": raw.get("status_detail", ""),
        "resource_uid": resource_uid,
        "region": region,
        "raw": raw,
    }


# Module-level singleton
scanner = ProwlerScanner()
