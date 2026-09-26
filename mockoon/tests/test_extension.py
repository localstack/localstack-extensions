import copy
import json
from pathlib import Path

import pytest
import requests

# Note: these tests assume that LocalStack has been started with the sample environment, i.e.,
#   MOCKOON_DATA=<path>/sample-app/environment.json

MOCKOON_URL = "http://mockoon.localhost.localstack.cloud:4566"
ADMIN_API_TOKEN = "test"
ENVIRONMENT_FILE = Path(__file__).parent.parent / "sample-app" / "environment.json"


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {ADMIN_API_TOKEN}"}


def test_get_templated_response():
    response = requests.get(f"{MOCKOON_URL}/orders/order-123")
    assert response.status_code == 200
    order = response.json()
    assert order["id"] == "order-123"
    assert order["status"] == "shipped"
    assert order["customer"] == {"first_name": "Jane", "last_name": "Doe"}


def test_response_rules():
    response = requests.get(f"{MOCKOON_URL}/orders/unknown")
    assert response.status_code == 404
    assert response.json() == {"message": "Order not found"}


def test_post_request_body_templating():
    response = requests.post(f"{MOCKOON_URL}/orders", json={"sku": "SKU-42"})
    assert response.status_code == 201
    assert response.json() == {"id": "ord-123", "status": "created", "sku": "SKU-42"}


def test_unknown_route():
    response = requests.get(f"{MOCKOON_URL}/does-not-exist")
    assert response.status_code == 404


def test_admin_api_requires_token(admin_headers):
    response = requests.get(f"{MOCKOON_URL}/mockoon-admin/logs")
    assert response.status_code == 401

    response = requests.get(f"{MOCKOON_URL}/mockoon-admin/logs", headers=admin_headers)
    assert response.status_code == 200


def test_admin_api_transaction_logs(admin_headers):
    requests.get(f"{MOCKOON_URL}/orders/logged-order")

    response = requests.get(f"{MOCKOON_URL}/mockoon-admin/logs", headers=admin_headers)
    assert response.status_code == 200
    paths = [log["request"]["urlPath"] for log in response.json()]
    assert "/orders/logged-order" in paths


def test_admin_api_global_vars(admin_headers):
    url = f"{MOCKOON_URL}/mockoon-admin/global-vars"
    response = requests.post(
        url, json={"key": "myVar", "value": "value123"}, headers=admin_headers
    )
    assert response.status_code == 200

    response = requests.get(f"{url}/myVar", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {"key": "myVar", "value": "value123"}

    requests.post(f"{url}/purge", headers=admin_headers)


def test_update_environment_at_runtime(admin_headers):
    environment = json.loads(ENVIRONMENT_FILE.read_text())
    updated = copy.deepcopy(environment)
    route_response = updated["routes"][0]["responses"][0]
    route_response["statusCode"] = 202
    route_response["body"] = json.dumps(
        {"id": "{{urlParam 'orderId'}}", "status": "updated"}
    )

    url = f"{MOCKOON_URL}/mockoon-admin/environment"
    try:
        response = requests.put(url, json=updated, headers=admin_headers)
        assert response.status_code == 200

        response = requests.get(f"{MOCKOON_URL}/orders/42")
        assert response.status_code == 202
        assert response.json() == {"id": "42", "status": "updated"}
    finally:
        # restore the original environment
        response = requests.put(url, json=environment, headers=admin_headers)
        assert response.status_code == 200

    response = requests.get(f"{MOCKOON_URL}/orders/42")
    assert response.status_code == 200
    assert response.json()["status"] == "shipped"
