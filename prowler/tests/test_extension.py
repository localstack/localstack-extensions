"""
Integration tests for the LocalStack Prowler extension.

Requires:
  - LocalStack running with the prowler extension installed
  - boto3 and requests available in the test environment

Run with:
    pytest tests/test_extension.py -v -s
"""
import time
import uuid

import boto3
import pytest
import requests

LOCALSTACK_ENDPOINT = "http://localhost:4566"
EXTENSION_BASE = f"{LOCALSTACK_ENDPOINT}/_extension/prowler"

SCAN_TIMEOUT = 360  # seconds; Prowler S3 scans typically complete in ~2-3 minutes


# Helpers

def _short_uid() -> str:
    return uuid.uuid4().hex[:8]


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )


def _wait_for_scan(timeout: int = SCAN_TIMEOUT, poll: int = 5) -> dict:
    """Poll /api/status until the active scan reaches a terminal state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{EXTENSION_BASE}/api/status", timeout=10)
        resp.raise_for_status()
        state = resp.json()
        if state["status"] in ("completed", "failed"):
            return state
        time.sleep(poll)
    pytest.fail(f"Scan did not reach a terminal state within {timeout}s")


def _wait_for_no_running_scan(timeout: int = SCAN_TIMEOUT, poll: int = 5) -> None:
    """Wait until the extension is ready to start a new scan."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{EXTENSION_BASE}/api/status", timeout=10)
        resp.raise_for_status()
        if resp.json().get("status") != "running":
            return
        time.sleep(poll)
    pytest.fail(f"Another scan remained in progress for over {timeout}s")


# Tests

def test_status_endpoint_is_reachable():
    """Extension API must respond and return a well-formed state object."""
    resp = requests.get(f"{EXTENSION_BASE}/api/status", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("idle", "running", "completed", "failed")
    assert "summary" in data


def test_start_scan_rejects_unknown_service():
    """Unknown service names must be rejected with HTTP 400."""
    resp = requests.post(
        f"{EXTENSION_BASE}/api/scans",
        json={"services": ["definitely-not-a-service"], "severity": []},
        timeout=10,
    )
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_start_scan_rejects_non_list_services():
    """Passing a string instead of a list for 'services' must return 400."""
    resp = requests.post(
        f"{EXTENSION_BASE}/api/scans",
        json={"services": "s3", "severity": []},
        timeout=10,
    )
    assert resp.status_code == 400


def test_start_scan_rejects_non_string_service_items():
    """Passing objects inside the 'services' list must return 400, not 500."""
    resp = requests.post(
        f"{EXTENSION_BASE}/api/scans",
        json={"services": [{"bucket": "x"}], "severity": []},
        timeout=10,
    )
    assert resp.status_code == 400


def test_start_scan_rejects_unknown_severity():
    """Unknown severity values must be rejected with HTTP 400."""
    resp = requests.post(
        f"{EXTENSION_BASE}/api/scans",
        json={"services": [], "severity": ["super-critical"]},
        timeout=10,
    )
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_s3_scan_finds_insecure_bucket():
    """
    End-to-end test:
      1. Create an intentionally insecure S3 bucket in LocalStack.
      2. Start an S3-scoped Prowler scan via the extension API.
      3. Verify a concurrent scan is rejected with 409.
      4. Wait for the scan to complete.
      5. Assert that findings are returned and contain the expected structure.
    """
    s3 = _s3_client()
    bucket_name = f"prowler-insecure-{_short_uid()}"
    _wait_for_no_running_scan()

    # Create a bucket with public access enabled — this is what Prowler will flag.
    s3.create_bucket(Bucket=bucket_name)
    s3.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        },
    )

    try:
        # Start the scan
        start_resp = requests.post(
            f"{EXTENSION_BASE}/api/scans",
            json={"services": ["s3"], "severity": []},
            timeout=10,
        )
        assert start_resp.status_code == 202, start_resp.text
        scan_data = start_resp.json()
        assert "scan_id" in scan_data
        assert scan_data["status"] == "running"
        scan_id = scan_data["scan_id"]

        # Concurrent scan must be blocked
        conflict_resp = requests.post(
            f"{EXTENSION_BASE}/api/scans",
            json={"services": ["s3"]},
            timeout=10,
        )
        assert conflict_resp.status_code == 409

        # Poll until done
        final_state = _wait_for_scan()
        assert final_state["status"] == "completed", f"Scan ended in unexpected state: {final_state}"

        # Validate findings
        latest_resp = requests.get(f"{EXTENSION_BASE}/api/scans/latest", timeout=10)
        assert latest_resp.status_code == 200
        result = latest_resp.json()

        assert result["scan_id"] == scan_id
        assert result["status"] == "completed"
        assert len(result["findings"]) > 0, "Expected findings but got none"

        # Every finding must have the required fields with valid values.
        for finding in result["findings"]:
            assert "check_id" in finding
            assert "check_title" in finding
            assert "service" in finding
            assert "severity" in finding
            assert "status" in finding
            assert "resource_uid" in finding
            assert "region" in finding
            assert finding["severity"] in ("critical", "high", "medium", "low", "informational")
            assert finding["status"] in ("PASS", "FAIL")

        # There must be at least one FAIL finding for the insecure bucket.
        fail_findings = [f for f in result["findings"] if f["status"] == "FAIL"]
        assert len(fail_findings) > 0, "Expected at least one FAIL finding"

        # Summary totals must match the findings list.
        summary = result.get("summary", {})
        assert summary.get("total") == len(result["findings"])
        assert summary.get("fail") == len(fail_findings)

    finally:
        s3.delete_bucket(Bucket=bucket_name)
