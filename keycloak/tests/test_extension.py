import json
import base64
import time
import pytest
import requests
import boto3
from botocore.config import Config


LOCALSTACK_URL = "http://localhost:4566"
KEYCLOAK_URL = "http://keycloak.localhost.localstack.cloud:4566"
KEYCLOAK_DIRECT_URL = "http://localhost:8080"  # Direct access to Keycloak HTTP port
KEYCLOAK_MGMT_URL = "http://localhost:9000"  # Health/metrics endpoint (Keycloak 26+)
DEFAULT_REALM = "localstack"
DEFAULT_CLIENT_ID = "localstack-client"
DEFAULT_CLIENT_SECRET = "localstack-client-secret"


def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verification (for testing claims)."""
    payload_b64 = token.split(".")[1]
    # Add padding if needed for base64url decoding
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def get_admin_token() -> str:
    """Get Keycloak admin token for API operations."""
    response = requests.post(
        f"{KEYCLOAK_DIRECT_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "admin",
            "password": "admin",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture
def admin_token():
    """Fixture providing admin token for Keycloak API operations."""
    return get_admin_token()


@pytest.fixture
def iam_client():
    """Create IAM client for LocalStack."""
    return boto3.client(
        "iam",
        endpoint_url=LOCALSTACK_URL,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
        config=Config(signature_version="v4"),
    )


@pytest.fixture
def sts_client():
    """Create STS client for LocalStack."""
    return boto3.client(
        "sts",
        endpoint_url=LOCALSTACK_URL,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
        config=Config(signature_version="v4"),
    )


class TestKeycloakHealth:
    """Tests for Keycloak health and accessibility."""

    def test_health_check_on_management_port(self):
        """Verify health endpoint on management port 9000 (Keycloak 26+)."""
        response = requests.get(f"{KEYCLOAK_MGMT_URL}/health/ready", timeout=10)
        assert response.status_code == 200
        assert response.json().get("status") == "UP"

    def test_default_realm_exists(self):
        """Verify default realm is created and accessible."""
        response = requests.get(f"{KEYCLOAK_URL}/realms/{DEFAULT_REALM}", timeout=10)
        assert response.status_code == 200
        assert response.json()["realm"] == DEFAULT_REALM

    def test_openid_configuration_available(self):
        """Verify OIDC discovery endpoint is available."""
        response = requests.get(
            f"{KEYCLOAK_URL}/realms/{DEFAULT_REALM}/.well-known/openid-configuration",
            timeout=10,
        )
        assert response.status_code == 200
        data = response.json()
        assert "token_endpoint" in data
        assert "jwks_uri" in data

    def test_jwks_endpoint_returns_keys(self):
        """Verify JWKS endpoint returns public keys for token validation."""
        response = requests.get(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/certs",
            timeout=10,
        )
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert len(data["keys"]) > 0
        assert "kty" in data["keys"][0]
        assert "kid" in data["keys"][0]


class TestTokenAcquisition:
    """Tests for token acquisition and validation."""

    def test_client_credentials_flow(self):
        """Verify tokens can be obtained using client credentials flow."""
        response = requests.post(
            f"{KEYCLOAK_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
            },
            timeout=30,
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"].lower() == "bearer"

    def test_token_has_correct_issuer(self):
        """Verify token issuer matches localhost:8080 (direct Keycloak URL)."""
        response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
            },
            timeout=30,
        )
        assert response.status_code == 200
        payload = decode_jwt_payload(response.json()["access_token"])
        assert payload["iss"] == f"http://localhost:8080/realms/{DEFAULT_REALM}"

    def test_token_has_valid_expiry(self):
        """Verify token has reasonable expiry time."""
        response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
            },
            timeout=30,
        )
        assert response.status_code == 200
        payload = decode_jwt_payload(response.json()["access_token"])
        assert payload["exp"] > time.time()
        assert payload["exp"] < time.time() + 86400


class TestServiceAccountRoles:
    """Tests for service account role configuration (fixes admin role issue)."""

    def test_service_account_has_admin_role(self):
        """Verify localstack-client service account has admin role for CRUD operations."""
        response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
            },
            timeout=30,
        )
        assert response.status_code == 200
        payload = decode_jwt_payload(response.json()["access_token"])
        roles = payload.get("realm_access", {}).get("roles", [])
        assert "admin" in roles, f"admin role not found: {roles}"
        assert "user" in roles, f"user role not found: {roles}"


class TestUserManagement:
    """Tests for user creation (fixes Keycloak 26+ profile requirements)."""

    def test_create_user_with_required_profile_fields(self, admin_token):
        """Verify user creation works with required Keycloak 26+ profile fields.
        
        Keycloak 26+ requires email, firstName, lastName for users to be "fully set up".
        Password must be set separately via reset-password endpoint.
        """
        test_username = "test_profile_user"
        headers = {"Authorization": f"Bearer {admin_token}"}
        users_url = f"{KEYCLOAK_DIRECT_URL}/admin/realms/{DEFAULT_REALM}/users"

        # Clean up if user exists
        existing = requests.get(
            users_url, headers=headers, params={"username": test_username}, timeout=10
        )
        if existing.ok and existing.json():
            user_id = existing.json()[0]["id"]
            requests.delete(f"{users_url}/{user_id}", headers=headers, timeout=10)

        # Create user with ALL required fields
        create_response = requests.post(
            users_url,
            headers=headers,
            json={
                "username": test_username,
                "enabled": True,
                "emailVerified": True,
                "email": f"{test_username}@test.local",
                "firstName": "Test",
                "lastName": "User",
                "requiredActions": [],
            },
            timeout=30,
        )
        assert create_response.status_code == 201

        # Get user ID
        get_response = requests.get(
            users_url, headers=headers, params={"username": test_username}, timeout=10
        )
        user_id = get_response.json()[0]["id"]

        # Set password SEPARATELY (required for Keycloak 26+)
        password_response = requests.put(
            f"{users_url}/{user_id}/reset-password",
            headers={**headers, "Content-Type": "application/json"},
            json={"type": "password", "value": "testpass123", "temporary": False},
            timeout=30,
        )
        assert password_response.status_code == 204

        # Verify password grant works
        token_response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
                "username": test_username,
                "password": "testpass123",
            },
            timeout=30,
        )
        assert token_response.status_code == 200

        # Cleanup
        requests.delete(f"{users_url}/{user_id}", headers=headers, timeout=10)

    def test_incomplete_user_fails_password_grant(self, admin_token):
        """Verify user without required profile fields gets 'Account not fully set up'."""
        test_username = "test_incomplete_user"
        headers = {"Authorization": f"Bearer {admin_token}"}
        users_url = f"{KEYCLOAK_DIRECT_URL}/admin/realms/{DEFAULT_REALM}/users"

        # Clean up if user exists
        existing = requests.get(
            users_url, headers=headers, params={"username": test_username}, timeout=10
        )
        if existing.ok and existing.json():
            user_id = existing.json()[0]["id"]
            requests.delete(f"{users_url}/{user_id}", headers=headers, timeout=10)

        # Create user WITHOUT required fields
        requests.post(
            users_url,
            headers=headers,
            json={"username": test_username, "enabled": True, "requiredActions": []},
            timeout=30,
        )

        # Get user ID and set password
        get_response = requests.get(
            users_url, headers=headers, params={"username": test_username}, timeout=10
        )
        user_id = get_response.json()[0]["id"]

        requests.put(
            f"{users_url}/{user_id}/reset-password",
            headers={**headers, "Content-Type": "application/json"},
            json={"type": "password", "value": "testpass123", "temporary": False},
            timeout=30,
        )

        # Password grant should fail
        token_response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
                "username": test_username,
                "password": "testpass123",
            },
            timeout=30,
        )
        assert token_response.status_code != 200
        assert "not fully set up" in token_response.json().get("error_description", "").lower()

        # Cleanup
        requests.delete(f"{users_url}/{user_id}", headers=headers, timeout=10)


class TestRealmConfiguration:
    """Tests for realm and client configuration."""

    def test_realm_has_required_roles(self, admin_token):
        """Verify default realm has admin and user roles."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{KEYCLOAK_DIRECT_URL}/admin/realms/{DEFAULT_REALM}/roles",
            headers=headers,
            timeout=10,
        )
        assert response.status_code == 200
        roles = [r["name"] for r in response.json()]
        assert "admin" in roles
        assert "user" in roles

    def test_client_configuration(self, admin_token):
        """Verify default client has correct settings."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{KEYCLOAK_DIRECT_URL}/admin/realms/{DEFAULT_REALM}/clients",
            headers=headers,
            params={"clientId": DEFAULT_CLIENT_ID},
            timeout=10,
        )
        assert response.status_code == 200
        client = response.json()[0]
        assert client["serviceAccountsEnabled"] is True
        assert client["directAccessGrantsEnabled"] is True

    def test_realm_ssl_not_required(self, admin_token):
        """Verify realm doesn't require SSL for local development."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{KEYCLOAK_DIRECT_URL}/admin/realms/{DEFAULT_REALM}",
            headers=headers,
            timeout=10,
        )
        assert response.status_code == 200
        assert response.json().get("sslRequired") == "none"


class TestOIDCIntegration:
    """Tests for OIDC provider integration with LocalStack."""

    def test_oidc_provider_registered(self, iam_client):
        """Verify OIDC provider is registered in LocalStack IAM with correct format."""
        response = iam_client.list_open_id_connect_providers()
        provider_arns = [p["Arn"] for p in response["OpenIDConnectProviderList"]]

        keycloak_arn = next((arn for arn in provider_arns if "keycloak" in arn), None)
        assert keycloak_arn is not None, f"No Keycloak provider found: {provider_arns}"
        assert f"realms/{DEFAULT_REALM}" in keycloak_arn

    def test_assume_role_with_web_identity(self, iam_client, sts_client):
        """Verify Keycloak tokens can be exchanged for AWS credentials."""
        # Get Keycloak access token
        token_response = requests.post(
            f"{KEYCLOAK_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
            },
            timeout=30,
        )
        assert token_response.status_code == 200
        access_token = token_response.json()["access_token"]

        # Create IAM role that trusts Keycloak OIDC provider
        role_name = "KeycloakTestRole"
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Federated": f"arn:aws:iam::000000000000:oidc-provider/keycloak.localhost.localstack.cloud:4566/realms/{DEFAULT_REALM}"
                    },
                    "Action": "sts:AssumeRoleWithWebIdentity",
                }
            ],
        }

        # Clean up and create role
        try:
            iam_client.delete_role(RoleName=role_name)
        except Exception:
            pass

        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
        )

        try:
            # Exchange Keycloak token for AWS credentials
            response = sts_client.assume_role_with_web_identity(
                RoleArn=f"arn:aws:iam::000000000000:role/{role_name}",
                RoleSessionName="test-session",
                WebIdentityToken=access_token,
            )
            assert "Credentials" in response
            assert "AccessKeyId" in response["Credentials"]
            assert "SecretAccessKey" in response["Credentials"]
            assert "SessionToken" in response["Credentials"]
        finally:
            iam_client.delete_role(RoleName=role_name)


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_credentials_returns_401(self):
        """Verify invalid credentials return proper error."""
        response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "invalid-client",
                "client_secret": "invalid-secret",
            },
            timeout=30,
        )
        assert response.status_code == 401
        assert "error" in response.json()

    def test_nonexistent_realm_returns_404(self):
        """Verify requests to non-existent realm return 404."""
        response = requests.get(
            f"{KEYCLOAK_DIRECT_URL}/realms/nonexistent-realm",
            timeout=10,
        )
        assert response.status_code == 404

    def test_invalid_grant_type_returns_400(self):
        """Verify invalid grant type returns proper error."""
        response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "invalid_grant",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
            },
            timeout=30,
        )
        assert response.status_code == 400
        assert "error" in response.json()


class TestEndToEndWorkflow:
    """End-to-end workflow test."""

    def test_keycloak_token_to_aws_api_call(self, iam_client, sts_client):
        """Test complete flow: Keycloak token -> AWS credentials -> API call."""
        # Step 1: Get Keycloak token
        token_response = requests.post(
            f"{KEYCLOAK_DIRECT_URL}/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": DEFAULT_CLIENT_ID,
                "client_secret": DEFAULT_CLIENT_SECRET,
            },
            timeout=30,
        )
        assert token_response.status_code == 200
        access_token = token_response.json()["access_token"]

        # Step 2: Create IAM role
        role_name = "E2ETestRole"
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Federated": f"arn:aws:iam::000000000000:oidc-provider/keycloak.localhost.localstack.cloud:4566/realms/{DEFAULT_REALM}"
                    },
                    "Action": "sts:AssumeRoleWithWebIdentity",
                }
            ],
        }

        try:
            iam_client.delete_role(RoleName=role_name)
        except Exception:
            pass

        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
        )

        try:
            # Step 3: Exchange token for AWS credentials
            response = sts_client.assume_role_with_web_identity(
                RoleArn=f"arn:aws:iam::000000000000:role/{role_name}",
                RoleSessionName="e2e-session",
                WebIdentityToken=access_token,
            )
            credentials = response["Credentials"]

            # Step 4: Use temporary credentials
            temp_sts = boto3.client(
                "sts",
                endpoint_url=LOCALSTACK_URL,
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name="us-east-1",
            )

            identity = temp_sts.get_caller_identity()
            assert role_name in identity["Arn"]
        finally:
            iam_client.delete_role(RoleName=role_name)
