"""
Lambda function for User CRUD operations.

This function handles:
- GET /users - List all users
- POST /users - Create a new user
- GET /users/{username} - Get a specific user
- PUT /users/{username} - Update a user
- DELETE /users/{username} - Delete a user

Authorization context (roles, username) is passed from the Lambda authorizer.
"""

import json
import os
from datetime import datetime
from typing import Any

import boto3

# Configuration
USERS_TABLE = os.environ.get("USERS_TABLE", "keycloak-sample-users")
LOCALSTACK_HOSTNAME = os.environ.get("LOCALSTACK_HOSTNAME", "localhost")
EDGE_PORT = os.environ.get("EDGE_PORT", "4566")

# DynamoDB client
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=f"http://{LOCALSTACK_HOSTNAME}:{EDGE_PORT}",
    region_name="us-east-1",
)
table = dynamodb.Table(USERS_TABLE)


def response(status_code: int, body: Any) -> dict:
    """Build HTTP response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def get_auth_context(event: dict) -> dict:
    """Extract authorization context from the event."""
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})

    return {
        "username": authorizer.get("username", "unknown"),
        "roles": authorizer.get("roles", "").split(",")
        if authorizer.get("roles")
        else [],
        "sub": authorizer.get("sub", ""),
    }


def has_role(auth_context: dict, role: str) -> bool:
    """Check if user has a specific role."""
    return role in auth_context.get("roles", [])


def is_admin(auth_context: dict) -> bool:
    """Check if user has admin role."""
    return has_role(auth_context, "admin")


def list_users(event: dict) -> dict:
    """List all users."""
    auth_context = get_auth_context(event)
    print(f"List users requested by: {auth_context['username']}")

    try:
        result = table.scan()
        users = result.get("Items", [])

        return response(
            200,
            {
                "users": users,
                "count": len(users),
            },
        )

    except Exception as e:
        print(f"Error listing users: {e}")
        return response(500, {"error": "Failed to list users"})


def get_user(event: dict, username: str) -> dict:
    """Get a specific user."""
    auth_context = get_auth_context(event)
    print(f"Get user '{username}' requested by: {auth_context['username']}")

    try:
        result = table.get_item(Key={"username": username})
        user = result.get("Item")

        if not user:
            return response(404, {"error": f"User '{username}' not found"})

        return response(200, user)

    except Exception as e:
        print(f"Error getting user: {e}")
        return response(500, {"error": "Failed to get user"})


def create_user(event: dict) -> dict:
    """Create a new user."""
    auth_context = get_auth_context(event)
    print(f"Create user requested by: {auth_context['username']}")

    # Check admin role for create
    if not is_admin(auth_context):
        return response(403, {"error": "Admin role required to create users"})

    try:
        body = json.loads(event.get("body", "{}"))

        if not body.get("username"):
            return response(400, {"error": "Username is required"})

        username = body["username"]

        # Check if user already exists
        existing = table.get_item(Key={"username": username})
        if existing.get("Item"):
            return response(409, {"error": f"User '{username}' already exists"})

        # Create user
        user = {
            "username": username,
            "email": body.get("email", ""),
            "name": body.get("name", ""),
            "created_at": datetime.utcnow().isoformat(),
            "created_by": auth_context["username"],
        }

        table.put_item(Item=user)

        return response(201, user)

    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON body"})
    except Exception as e:
        print(f"Error creating user: {e}")
        return response(500, {"error": "Failed to create user"})


def update_user(event: dict, username: str) -> dict:
    """Update an existing user."""
    auth_context = get_auth_context(event)
    print(f"Update user '{username}' requested by: {auth_context['username']}")

    # Check admin role for update
    if not is_admin(auth_context):
        return response(403, {"error": "Admin role required to update users"})

    try:
        body = json.loads(event.get("body", "{}"))

        # Check if user exists
        existing = table.get_item(Key={"username": username})
        if not existing.get("Item"):
            return response(404, {"error": f"User '{username}' not found"})

        # Update user
        update_expression = "SET updated_at = :updated_at, updated_by = :updated_by"
        expression_values = {
            ":updated_at": datetime.utcnow().isoformat(),
            ":updated_by": auth_context["username"],
        }

        if "email" in body:
            update_expression += ", email = :email"
            expression_values[":email"] = body["email"]

        if "name" in body:
            update_expression += ", #name = :name"
            expression_values[":name"] = body["name"]

        update_params = {
            "Key": {"username": username},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_values,
            "ReturnValues": "ALL_NEW",
        }

        # Handle reserved word 'name'
        if "name" in body:
            update_params["ExpressionAttributeNames"] = {"#name": "name"}

        result = table.update_item(**update_params)

        return response(200, result["Attributes"])

    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON body"})
    except Exception as e:
        print(f"Error updating user: {e}")
        return response(500, {"error": "Failed to update user"})


def delete_user(event: dict, username: str) -> dict:
    """Delete a user."""
    auth_context = get_auth_context(event)
    print(f"Delete user '{username}' requested by: {auth_context['username']}")

    # Check admin role for delete
    if not is_admin(auth_context):
        return response(403, {"error": "Admin role required to delete users"})

    try:
        # Check if user exists
        existing = table.get_item(Key={"username": username})
        if not existing.get("Item"):
            return response(404, {"error": f"User '{username}' not found"})

        table.delete_item(Key={"username": username})

        return response(200, {"message": f"User '{username}' deleted"})

    except Exception as e:
        print(f"Error deleting user: {e}")
        return response(500, {"error": "Failed to delete user"})


def handler(event: dict, context: Any) -> dict:
    """Main Lambda handler."""
    print(f"Event: {json.dumps(event)}")

    http_method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    # Route request
    if path == "/users":
        if http_method == "GET":
            return list_users(event)
        elif http_method == "POST":
            return create_user(event)

    elif path.startswith("/users/") and path_params.get("username"):
        username = path_params["username"]

        if http_method == "GET":
            return get_user(event, username)
        elif http_method == "PUT":
            return update_user(event, username)
        elif http_method == "DELETE":
            return delete_user(event, username)

    return response(404, {"error": "Not found"})
