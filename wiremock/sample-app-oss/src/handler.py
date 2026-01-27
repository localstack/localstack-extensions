import json
import requests


def get_time_off(event, context):
    """
    Handles the API Gateway event, fetches data from the mock Personio API,
    and returns a transformed JSON response.
    """
    try:
        # Define the mock API endpoint URL (hardcoding `wiremock.localhost.localstack.cloud` for
        # local dev for now - could be injected via env variables in the future ...)
        url = "http://wiremock.localhost.localstack.cloud:4566/company/time-offs/534813865"

        # Make a GET request to the mock API
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        data = response.json()

        # Safely extract data using .get() to avoid KeyErrors
        employee_data = data.get("data", {}).get("employee", {}).get("attributes", {})
        time_off_attributes = data.get("data", {}).get("attributes", {})

        # Transform the data into the desired response format
        transformed_data = {
            "employee_name": f"{employee_data.get('first_name', 'N/A')} {employee_data.get('last_name', 'N/A')}",
            "time_off_date": f"{time_off_attributes.get('start_date', 'N/A')} to {time_off_attributes.get('end_date', 'N/A')}",
            "approval_status": time_off_attributes.get("status", "N/A"),
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(transformed_data),
        }

    except requests.exceptions.RequestException as e:
        # Handle network-related errors (e.g., connection refused, timeout)
        error_message = {
            "message": "Could not connect to the downstream HR service.",
            "error": str(e),
        }
        print("Error:", error_message)
        return {
            "statusCode": 503,  # Service Unavailable
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(error_message),
        }
    except Exception as e:
        # Handle other unexpected errors (e.g., JSON parsing issues, programming errors)
        error_message = {"message": "An unexpected error occurred.", "error": str(e)}
        print("Error:", error_message)
        return {
            "statusCode": 500,  # Internal Server Error
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(error_message),
        }
