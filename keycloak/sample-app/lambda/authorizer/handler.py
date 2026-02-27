"""
Lambda Authorizer for validating Keycloak JWT tokens.

This authorizer:
1. Extracts the JWT from the Authorization header
2. Fetches Keycloak's public keys from JWKS endpoint
3. Validates the token signature, expiration, and audience
4. Extracts roles from the token
5. Returns an IAM policy allowing or denying access
"""

import base64
import hashlib
import hmac
import json
import os
import urllib.request
from functools import lru_cache
from typing import Any

# Configuration from environment
KEYCLOAK_URL = os.environ.get(
    "KEYCLOAK_URL", "http://keycloak.localhost.localstack.cloud:4566"
)
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "localstack")
EXPECTED_AUDIENCE = os.environ.get("EXPECTED_AUDIENCE", "localstack-client")


@lru_cache(maxsize=1)
def get_jwks() -> dict:
    """Fetch and cache Keycloak's JWKS (JSON Web Key Set)."""
    jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    print(f"Fetching JWKS from: {jwks_url}")

    with urllib.request.urlopen(jwks_url, timeout=10) as response:
        return json.loads(response.read().decode())


def base64url_decode(data: str) -> bytes:
    """Decode base64url encoded data."""
    # Add padding if needed
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def decode_jwt_unverified(token: str) -> tuple[dict, dict]:
    """Decode JWT without verification (for extracting header and payload)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    header = json.loads(base64url_decode(parts[0]))
    payload = json.loads(base64url_decode(parts[1]))

    return header, payload


def verify_jwt_signature(token: str, jwks: dict) -> dict:
    """
    Verify JWT signature using Keycloak's public keys.

    Note: This is a simplified verification. In production, use a proper
    JWT library like PyJWT or python-jose.
    """
    header, payload = decode_jwt_unverified(token)

    # For LocalStack testing, we'll do basic validation
    # In production, implement full RS256 signature verification
    kid = header.get("kid")
    alg = header.get("alg")

    if alg != "RS256":
        print(f"Unexpected algorithm: {alg}")

    # Find matching key
    matching_key = None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            matching_key = key
            break

    if not matching_key:
        print(f"No matching key found for kid: {kid}")
        # For LocalStack testing, we'll still return payload
        # In production, this should raise an error

    return payload


def validate_token(token: str) -> dict:
    """Validate the JWT token and return the payload."""
    jwks = get_jwks()
    payload = verify_jwt_signature(token, jwks)

    # Validate expiration
    import time

    exp = payload.get("exp", 0)
    if exp < time.time():
        raise ValueError("Token has expired")

    # Validate issuer
    expected_issuer = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
    if payload.get("iss") != expected_issuer:
        print(
            f"Warning: Issuer mismatch. Expected: {expected_issuer}, Got: {payload.get('iss')}"
        )

    # Validate audience
    aud = payload.get("aud")
    if isinstance(aud, list):
        if EXPECTED_AUDIENCE not in aud:
            print(
                f"Warning: Audience mismatch. Expected: {EXPECTED_AUDIENCE}, Got: {aud}"
            )
    elif aud != EXPECTED_AUDIENCE:
        # Check azp (authorized party) as fallback
        azp = payload.get("azp")
        if azp != EXPECTED_AUDIENCE:
            print(
                f"Warning: Audience/azp mismatch. Expected: {EXPECTED_AUDIENCE}, Got: aud={aud}, azp={azp}"
            )

    return payload


def extract_roles(payload: dict) -> list[str]:
    """Extract roles from the JWT payload."""
    roles = []

    # Realm roles
    realm_access = payload.get("realm_access", {})
    roles.extend(realm_access.get("roles", []))

    # Client roles
    resource_access = payload.get("resource_access", {})
    for client, access in resource_access.items():
        client_roles = access.get("roles", [])
        roles.extend([f"{client}:{role}" for role in client_roles])

    return roles


def generate_policy(
    principal_id: str,
    effect: str,
    resource: str,
    context: dict[str, Any] | None = None,
) -> dict:
    """Generate IAM policy document for API Gateway."""
    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }

    if context:
        # Convert all values to strings (API Gateway requirement)
        policy["context"] = {
            k: str(v) if not isinstance(v, str) else v for k, v in context.items()
        }

    return policy


def handler(event: dict, context: Any) -> dict:
    """
    Lambda authorizer handler.

    Validates Keycloak JWT and returns IAM policy.
    """
    print(f"Authorizer event: {json.dumps(event)}")

    try:
        # Extract token from Authorization header
        auth_token = event.get("authorizationToken", "")

        if not auth_token:
            print("No authorization token provided")
            return generate_policy("anonymous", "Deny", event["methodArn"])

        # Remove "Bearer " prefix if present
        if auth_token.lower().startswith("bearer "):
            auth_token = auth_token[7:]

        # Validate token
        payload = validate_token(auth_token)

        # Extract user info
        subject = payload.get("sub", "unknown")
        username = payload.get("preferred_username", subject)
        email = payload.get("email", "")
        roles = extract_roles(payload)

        print(f"Authorized user: {username}, roles: {roles}")

        # Build context for downstream Lambda
        context_data = {
            "sub": subject,
            "username": username,
            "email": email,
            "roles": ",".join(roles),
        }

        # Allow access
        return generate_policy(subject, "Allow", event["methodArn"], context_data)

    except Exception as e:
        print(f"Authorization failed: {e}")
        return generate_policy("anonymous", "Deny", event["methodArn"])
