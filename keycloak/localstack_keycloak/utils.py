"""Utility functions for Keycloak extension."""

import os

# Environment variable names
ENV_KEYCLOAK_REALM = "KEYCLOAK_REALM"
ENV_KEYCLOAK_VERSION = "KEYCLOAK_VERSION"
ENV_KEYCLOAK_REALM_FILE = "KEYCLOAK_REALM_FILE"
ENV_KEYCLOAK_DEFAULT_USER = "KEYCLOAK_DEFAULT_USER"
ENV_KEYCLOAK_DEFAULT_PASSWORD = "KEYCLOAK_DEFAULT_PASSWORD"
ENV_KEYCLOAK_OIDC_AUDIENCE = "KEYCLOAK_OIDC_AUDIENCE"
ENV_KEYCLOAK_FLAGS = "KEYCLOAK_FLAGS"

# Default values
DEFAULT_REALM = "localstack"
DEFAULT_VERSION = "26.0"
DEFAULT_AUDIENCE = "localstack-client"
DEFAULT_CLIENT_SECRET = "localstack-client-secret"

# Ports
KEYCLOAK_HTTP_PORT = 8080
KEYCLOAK_MGMT_PORT = 9000


def get_env(name: str, default: str = None) -> str:
    """Get environment variable, checking both LOCALSTACK_ prefixed and non-prefixed versions."""
    prefixed = f"LOCALSTACK_{name}"
    value = os.environ.get(prefixed)
    if value:
        return value
    return os.environ.get(name, default)


def get_default_realm_config(realm_name: str = DEFAULT_REALM) -> dict:
    """Get the default realm configuration."""
    return {
        "realm": realm_name,
        "enabled": True,
        "sslRequired": "none",
        "registrationAllowed": True,
        "loginWithEmailAllowed": True,
        "resetPasswordAllowed": True,
        "accessTokenLifespan": 3600,
        "ssoSessionIdleTimeout": 1800,
        "roles": {
            "realm": [
                {"name": "admin", "description": "Administrator role"},
                {"name": "user", "description": "Regular user role"},
            ]
        },
        "defaultRoles": ["user"],
    }


def get_default_client_config(audience: str = DEFAULT_AUDIENCE) -> dict:
    """Get the default client configuration."""
    return {
        "clientId": audience,
        "name": "LocalStack Client",
        "enabled": True,
        "clientAuthenticatorType": "client-secret",
        "secret": DEFAULT_CLIENT_SECRET,
        "publicClient": False,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": True,
        "protocol": "openid-connect",
        "redirectUris": ["*"],
        "webOrigins": ["*"],
    }
