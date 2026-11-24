import base64

import boto3
import requests
from localstack.utils.strings import short_uid


# Vault connection details
VAULT_ADDR = "http://vault.localhost.localstack.cloud:4566"
VAULT_TOKEN = "root"
LOCALSTACK_ENDPOINT = "http://localhost:4566"


def vault_request(method, path, data=None, token=VAULT_TOKEN):
    """Make a request to Vault API."""
    url = f"{VAULT_ADDR}/v1/{path}"
    headers = {"X-Vault-Token": token}
    if data:
        headers["Content-Type"] = "application/json"
        return requests.request(method, url, headers=headers, json=data)
    return requests.request(method, url, headers=headers)


def test_vault_health():
    """Test that Vault is running and healthy."""
    response = requests.get(f"{VAULT_ADDR}/v1/sys/health")
    assert response.status_code == 200

    data = response.json()
    assert data["initialized"] is True
    assert data["sealed"] is False


def test_vault_auth_with_token():
    """Test authentication with root token."""
    response = vault_request("GET", "auth/token/lookup-self")
    assert response.status_code == 200

    data = response.json()
    assert "data" in data
    assert data["data"]["id"] == VAULT_TOKEN


def test_kv_secrets_engine():
    """Test KV v2 secrets engine operations."""
    secret_path = f"myapp/config-{short_uid()}"

    # Write a secret
    secret_data = {
        "data": {
            "api_key": "test-api-key-123",
            "db_password": "supersecret",
        }
    }
    response = vault_request("POST", f"secret/data/{secret_path}", secret_data)
    assert response.status_code == 200

    # Read the secret back
    response = vault_request("GET", f"secret/data/{secret_path}")
    assert response.status_code == 200

    data = response.json()
    assert data["data"]["data"]["api_key"] == "test-api-key-123"
    assert data["data"]["data"]["db_password"] == "supersecret"

    # Delete the secret
    response = vault_request("DELETE", f"secret/data/{secret_path}")
    assert response.status_code == 204


def test_kv_list_secrets():
    """Test listing secrets in KV engine."""
    # Create a few secrets
    for i in range(3):
        secret_data = {"data": {"value": f"secret-{i}"}}
        vault_request("POST", f"secret/data/list-test/item-{i}", secret_data)

    # List secrets
    response = vault_request("LIST", "secret/metadata/list-test")
    assert response.status_code == 200

    data = response.json()
    keys = data["data"]["keys"]
    assert len(keys) == 3
    assert "item-0" in keys
    assert "item-1" in keys
    assert "item-2" in keys

    # Cleanup
    for i in range(3):
        vault_request("DELETE", f"secret/metadata/list-test/item-{i}")


def test_transit_engine():
    """Test Transit secrets engine for encryption."""
    key_name = f"test-key-{short_uid()}"

    # Create an encryption key
    response = vault_request("POST", f"transit/keys/{key_name}")
    assert response.status_code in (200, 204)  # Vault may return either

    # Encrypt some data
    plaintext = "Hello, Vault!"
    plaintext_b64 = base64.b64encode(plaintext.encode()).decode()

    response = vault_request(
        "POST",
        f"transit/encrypt/{key_name}",
        {"plaintext": plaintext_b64},
    )
    assert response.status_code == 200
    ciphertext = response.json()["data"]["ciphertext"]
    assert ciphertext.startswith("vault:v1:")

    # Decrypt the data
    response = vault_request(
        "POST",
        f"transit/decrypt/{key_name}",
        {"ciphertext": ciphertext},
    )
    assert response.status_code == 200
    decrypted_b64 = response.json()["data"]["plaintext"]
    decrypted = base64.b64decode(decrypted_b64).decode()
    assert decrypted == plaintext

    # Delete the key
    vault_request("POST", f"transit/keys/{key_name}/config", {"deletion_allowed": True})
    vault_request("DELETE", f"transit/keys/{key_name}")


def test_aws_auth_method_enabled():
    """Test that AWS auth method is enabled and configured."""
    response = vault_request("GET", "sys/auth")
    assert response.status_code == 200

    data = response.json()
    assert "aws/" in data["data"]
    assert data["data"]["aws/"]["type"] == "aws"


def test_default_lambda_role_exists():
    """Test that the default Lambda IAM auth role exists or can be created."""
    response = vault_request("GET", "auth/aws/role/default-lambda-role")

    # If role doesn't exist (e.g., after Terraform testing), create it
    if response.status_code == 404:
        role_config = {
            "auth_type": "iam",
            "bound_iam_principal_arn": ["arn:aws:iam::000000000000:role/*"],
            "token_policies": ["default-lambda-policy"],
            "resolve_aws_unique_ids": False,
        }
        create_response = vault_request(
            "POST", "auth/aws/role/default-lambda-role", role_config
        )
        assert create_response.status_code == 204
        response = vault_request("GET", "auth/aws/role/default-lambda-role")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["auth_type"] == "iam"
    assert data["data"]["resolve_aws_unique_ids"] is False


def test_default_lambda_policy_exists():
    """Test that the default Lambda policy exists with correct permissions."""
    response = vault_request("GET", "sys/policies/acl/default-lambda-policy")
    assert response.status_code == 200

    data = response.json()
    policy = data["data"]["policy"]
    assert "secret/*" in policy
    assert "transit/*" in policy


def test_mixed_vault_and_aws_traffic():
    """
    Test that Vault HTTP traffic and AWS API traffic work together.

    This verifies that the Vault extension properly proxies Vault requests
    while not interfering with regular AWS API requests.
    """
    # Test Vault API
    response = vault_request("GET", "sys/health")
    assert response.status_code == 200
    assert response.json()["sealed"] is False

    # Test AWS S3 API
    s3_client = boto3.client(
        "s3",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )

    bucket_name = f"vault-test-bucket-{short_uid()}"
    s3_client.create_bucket(Bucket=bucket_name)

    buckets = s3_client.list_buckets()
    bucket_names = [b["Name"] for b in buckets["Buckets"]]
    assert bucket_name in bucket_names

    # Cleanup
    s3_client.delete_bucket(Bucket=bucket_name)

    # Test AWS STS API (used by Vault for IAM auth)
    sts_client = boto3.client(
        "sts",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )

    identity = sts_client.get_caller_identity()
    assert "Account" in identity
    assert "Arn" in identity

    # Verify Vault still works after AWS calls
    response = vault_request("GET", "auth/token/lookup-self")
    assert response.status_code == 200


def test_create_custom_policy_and_role():
    """Test creating custom Vault policies and IAM auth roles."""
    policy_name = f"custom-policy-{short_uid()}"
    role_name = f"custom-role-{short_uid()}"

    # Create a custom policy
    policy_hcl = """
    path "secret/data/custom/*" {
      capabilities = ["read"]
    }
    """
    response = vault_request(
        "PUT", f"sys/policies/acl/{policy_name}", {"policy": policy_hcl}
    )
    assert response.status_code == 204

    # Create a custom IAM auth role
    role_config = {
        "auth_type": "iam",
        "bound_iam_principal_arn": [
            "arn:aws:iam::000000000000:role/custom-lambda-role"
        ],
        "token_policies": [policy_name],
        "resolve_aws_unique_ids": False,
    }
    response = vault_request("POST", f"auth/aws/role/{role_name}", role_config)
    assert response.status_code == 204

    # Verify the role was created
    response = vault_request("GET", f"auth/aws/role/{role_name}")
    assert response.status_code == 200
    assert policy_name in response.json()["data"]["token_policies"]

    # Cleanup
    vault_request("DELETE", f"auth/aws/role/{role_name}")
    vault_request("DELETE", f"sys/policies/acl/{policy_name}")
