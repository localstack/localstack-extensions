import logging
import os
import time

import hvac
import requests

from localstack import config, constants
from localstack.utils.net import get_addressable_container_host
from localstack_extensions.utils.docker import ProxiedDockerContainerExtension

LOG = logging.getLogger(__name__)

# Environment variables
ENV_VAULT_ROOT_TOKEN = "VAULT_ROOT_TOKEN"
ENV_VAULT_PORT = "VAULT_PORT"

# Defaults
DEFAULT_ROOT_TOKEN = "root"
DEFAULT_PORT = 8200


class VaultExtension(ProxiedDockerContainerExtension):
    """
    HashiCorp Vault Extension for LocalStack.

    Runs Vault in dev mode with:
    - KV v2 secrets engine at secret/
    - Transit secrets engine at transit/
    - IAM auth method pre-configured to accept any Lambda role
    """

    name = "localstack-vault"

    HOST = "vault.<domain>"
    DOCKER_IMAGE = "hashicorp/vault:latest"

    def __init__(self):
        self.root_token = os.getenv(ENV_VAULT_ROOT_TOKEN, DEFAULT_ROOT_TOKEN)
        self.vault_port = int(os.getenv(ENV_VAULT_PORT, DEFAULT_PORT))

        env_vars = {
            "VAULT_DEV_ROOT_TOKEN_ID": self.root_token,
            "VAULT_DEV_LISTEN_ADDRESS": f"0.0.0.0:{self.vault_port}",
            "VAULT_LOG_LEVEL": "info",
        }

        def _health_check():
            """Check if Vault is initialized and unsealed."""
            container_host = get_addressable_container_host()
            health_url = f"http://{container_host}:{self.vault_port}/v1/sys/health"
            LOG.debug("Vault health check: %s", health_url)
            response = requests.get(health_url, timeout=5)
            # Vault returns 200 when initialized, unsealed, and active
            # In dev mode, it should always be ready
            assert response.status_code == 200, f"Vault not ready: {response.status_code}"

        super().__init__(
            image_name=self.DOCKER_IMAGE,
            container_ports=[self.vault_port],
            host=self.HOST,
            env_vars=env_vars,
            health_check_fn=_health_check,
            health_check_retries=60,
            health_check_sleep=1.0,
        )

    def on_platform_ready(self):
        """Configure Vault after it's running and LocalStack is ready."""
        try:
            self._configure_vault()
        except Exception as e:
            LOG.error("Failed to configure Vault: %s", e)
            raise

        url = f"http://vault.{constants.LOCALHOST_HOSTNAME}:{config.get_edge_port_http()}"
        LOG.info("Vault extension ready: %s", url)
        LOG.info("Root token: %s", self.root_token)

    def _configure_vault(self):
        """Set up Vault with KV v2, Transit, and IAM auth."""
        container_host = get_addressable_container_host()
        vault_addr = f"http://{container_host}:{self.vault_port}"

        # Wait a moment for Vault to be fully ready for API calls
        time.sleep(1)

        client = hvac.Client(url=vault_addr, token=self.root_token)

        if not client.is_authenticated():
            raise RuntimeError("Failed to authenticate with Vault")

        LOG.info("Configuring Vault secrets engines and auth methods...")

        # KV v2 is enabled by default at secret/ in dev mode
        # Just verify it's there
        try:
            secrets_engines = client.sys.list_mounted_secrets_engines()
            if "secret/" in secrets_engines:
                LOG.debug("KV v2 secrets engine already mounted at secret/")
        except Exception as e:
            LOG.warning("Could not verify secrets engines: %s", e)

        # Enable Transit secrets engine
        self._enable_transit_engine(client)

        # Configure IAM auth method
        self._configure_iam_auth(client)

        # Create default Lambda policy
        self._create_default_policy(client)

        LOG.info("Vault configuration complete")

    def _enable_transit_engine(self, client: hvac.Client):
        """Enable the Transit secrets engine for encryption-as-a-service."""
        try:
            secrets_engines = client.sys.list_mounted_secrets_engines()
            if "transit/" not in secrets_engines:
                client.sys.enable_secrets_engine(
                    backend_type="transit",
                    path="transit",
                )
                LOG.info("Enabled Transit secrets engine at transit/")
            else:
                LOG.debug("Transit secrets engine already mounted")
        except Exception as e:
            LOG.warning("Could not enable Transit engine: %s", e)

    def _configure_iam_auth(self, client: hvac.Client):
        """Configure AWS IAM auth method to work with LocalStack."""
        try:
            # Enable AWS auth method
            auth_methods = client.sys.list_auth_methods()
            if "aws/" not in auth_methods:
                client.sys.enable_auth_method(
                    method_type="aws",
                    path="aws",
                )
                LOG.info("Enabled AWS auth method at aws/")

            # Configure the AWS auth to use LocalStack's STS endpoint
            localstack_endpoint = f"http://{get_addressable_container_host()}:{config.get_edge_port_http()}"

            client.auth.aws.configure(
                sts_endpoint=localstack_endpoint,
                sts_region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                iam_server_id_header_value="",
            )
            LOG.info("Configured AWS auth to use LocalStack STS: %s", localstack_endpoint)

            # Create a wildcard IAM role that accepts any Lambda
            # This role maps any IAM principal to the default-lambda-policy
            self._create_wildcard_iam_role(client)

        except Exception as e:
            LOG.warning("Could not configure IAM auth: %s", e)

    def _create_wildcard_iam_role(self, client: hvac.Client):
        """Create an IAM role that accepts any AWS principal from LocalStack."""
        role_name = "default-lambda-role"

        try:
            # Create a role that accepts any IAM role from LocalStack's account
            # Note: bound_iam_principal_arn="*" doesn't work in Vault - we need a
            # specific ARN pattern. LocalStack uses account 000000000000.
            # We also MUST set resolve_aws_unique_ids=false since Vault can't
            # resolve LocalStack IAM principals via AWS APIs.
            client.auth.aws.create_role(
                role=role_name,
                auth_type="iam",
                bound_iam_principal_arn=["arn:aws:iam::000000000000:role/*"],
                token_policies=["default-lambda-policy"],
                token_ttl="24h",
                token_max_ttl="24h",
                resolve_aws_unique_ids=False,  # Critical for LocalStack
            )
            LOG.info("Created IAM auth role: %s", role_name)
        except hvac.exceptions.InvalidRequest as e:
            if "already exists" in str(e).lower():
                LOG.debug("IAM role %s already exists", role_name)
            else:
                LOG.warning("Could not create IAM role %s: %s", role_name, e)
                raise

    def _create_default_policy(self, client: hvac.Client):
        """Create a default policy for Lambda functions."""
        policy_name = "default-lambda-policy"
        policy_hcl = """
# Default policy for Lambda functions using Vault
# Allows full access to secret/ and transit/ paths

path "secret/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/data/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/*" {
  capabilities = ["list", "read", "delete"]
}

path "transit/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "transit/encrypt/*" {
  capabilities = ["create", "update"]
}

path "transit/decrypt/*" {
  capabilities = ["create", "update"]
}
"""
        try:
            client.sys.create_or_update_policy(
                name=policy_name,
                policy=policy_hcl,
            )
            LOG.info("Created policy: %s", policy_name)
        except Exception as e:
            LOG.warning("Could not create policy %s: %s", policy_name, e)
