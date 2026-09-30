import json
import os

import requests

# URL of the mock Orders API served by Mockoon (can be overridden via env variable)
MOCKOON_URL = os.environ.get(
    "MOCKOON_URL", "http://mockoon.localhost.localstack.cloud:4566"
)


def get_order(event, context):
    """
    Handles the API Gateway event, fetches the order from the mock Orders API,
    and returns a transformed JSON response.
    """
    order_id = (event.get("pathParameters") or {}).get("orderId", "")
    try:
        response = requests.get(f"{MOCKOON_URL}/orders/{order_id}", timeout=5)
        if response.status_code == 404:
            return _response(404, {"message": f"Order {order_id} not found"})
        response.raise_for_status()

        order = response.json()
        customer = order.get("customer", {})
        items = order.get("items", [])

        # Transform the data into the desired response format
        result = {
            "order_id": order.get("id"),
            "customer_name": f"{customer.get('first_name', 'N/A')} {customer.get('last_name', 'N/A')}",
            "status": order.get("status", "N/A"),
            "item_count": sum(item.get("quantity", 0) for item in items),
            "total": order.get("total"),
        }
        return _response(200, result)

    except requests.exceptions.RequestException as e:
        # Handle network-related errors (e.g., connection refused, timeout)
        error_message = {
            "message": "Could not connect to the downstream Orders service.",
            "error": str(e),
        }
        print("Error:", error_message)
        return _response(503, error_message)
    except Exception as e:
        # Handle other unexpected errors (e.g., JSON parsing issues, programming errors)
        error_message = {"message": "An unexpected error occurred.", "error": str(e)}
        print("Error:", error_message)
        return _response(500, error_message)


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
