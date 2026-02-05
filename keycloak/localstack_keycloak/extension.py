"""Keycloak extension for LocalStack."""

import logging
import shlex

import requests
from localstack import config, constants
from localstack.utils.net import get_addressable_container_host
from localstack_extensions.utils.docker import ProxiedDockerContainerExtension

from .utils import (
    DEFAULT_CLIENT_SECRET,
    ENV_KEYCLOAK_DEFAULT_PASSWORD,
    ENV_KEYCLOAK_DEFAULT_USER,
    ENV_KEYCLOAK_FLAGS,
    ENV_KEYCLOAK_OIDC_AUDIENCE,
    ENV_KEYCLOAK_REALM,
    ENV_KEYCLOAK_REALM_FILE,
    ENV_KEYCLOAK_VERSION,
    KEYCLOAK_HTTP_PORT,
    KEYCLOAK_MGMT_PORT,
    DEFAULT_AUDIENCE,
    DEFAULT_REALM,
    DEFAULT_VERSION,
    get_default_client_config,
    get_default_realm_config,
    get_env,
)

LOG = logging.getLogger(__name__)


class KeycloakExtension(ProxiedDockerContainerExtension):
    """Keycloak extension for LocalStack."""

    name = "keycloak"
    HOST = "keycloak.<domain>"
    DOCKER_IMAGE = "quay.io/keycloak/keycloak"

    def __init__(self):
        self.realm = get_env(ENV_KEYCLOAK_REALM, DEFAULT_REALM)
        self.version = get_env(ENV_KEYCLOAK_VERSION, DEFAULT_VERSION)
        self.realm_file = get_env(ENV_KEYCLOAK_REALM_FILE)
        self.audience = get_env(ENV_KEYCLOAK_OIDC_AUDIENCE, DEFAULT_AUDIENCE)
        custom_flags = (get_env(ENV_KEYCLOAK_FLAGS) or "").strip()

        command = ["start-dev", "--health-enabled=true"]
        if self.realm_file:
            command.append("--import-realm")
        if custom_flags:
            command.extend(shlex.split(custom_flags))

        env_vars = {
            "KEYCLOAK_ADMIN": "admin",
            "KEYCLOAK_ADMIN_PASSWORD": "admin",
            "KC_HEALTH_ENABLED": "true",
            "KC_HTTP_ENABLED": "true",
            "KC_HOSTNAME_STRICT": "false",
        }

        volumes = None
        if self.realm_file:
            volumes = [(self.realm_file, "/opt/keycloak/data/import/realm.json")]

        super().__init__(
            image_name=f"{self.DOCKER_IMAGE}:{self.version}",
            container_ports=[KEYCLOAK_HTTP_PORT, KEYCLOAK_MGMT_PORT],
            host=self.HOST,
            command=command,
            env_vars=env_vars,
            volumes=volumes,
            health_check_fn=self._health_check,
            health_check_retries=90,
            health_check_sleep=2.0,
        )

    def _health_check(self):
        """Check Keycloak health on management port (9000 for Keycloak 26+)."""
        container_host = get_addressable_container_host()
        health_url = f"http://{container_host}:{KEYCLOAK_MGMT_PORT}/health/ready"
        response = requests.get(health_url, timeout=10)
        if not response.ok:
            raise Exception(f"Health check failed: {response.status_code}")

    def on_platform_ready(self):
        """Called when LocalStack platform is ready."""
        try:
            if not self.realm_file:
                self._create_default_realm()
            self._create_default_user()
            self._register_oidc_provider()
            self._log_startup_info()
        except Exception as e:
            LOG.error("Failed to complete Keycloak setup: %s", e)

    def _get_base_url(self) -> str:
        """Get Keycloak base URL."""
        return f"http://{get_addressable_container_host()}:{KEYCLOAK_HTTP_PORT}"

    def _get_admin_token(self) -> str:
        """Get admin access token."""
        response = requests.post(
            f"{self._get_base_url()}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": "admin",
            },
            timeout=30,
        )
        if not response.ok:
            raise Exception(f"Failed to get admin token: {response.text}")
        return response.json()["access_token"]

    def _create_default_realm(self):
        """Create the default realm via Admin API."""
        base_url = self._get_base_url()
        realm_url = f"{base_url}/realms/{self.realm}"

        if requests.get(realm_url, timeout=10).ok:
            LOG.info("Realm '%s' already exists", self.realm)
            return

        LOG.info("Creating realm: %s", self.realm)
        admin_token = self._get_admin_token()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{base_url}/admin/realms",
            headers=headers,
            json=get_default_realm_config(self.realm),
            timeout=30,
        )

        if response.status_code == 201:
            LOG.info("Created realm: %s", self.realm)
            self._create_default_client(admin_token)
        elif response.status_code != 409:
            LOG.warning("Failed to create realm: %s", response.text)

    def _create_default_client(self, admin_token: str):
        """Create the default client."""
        base_url = self._get_base_url()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{base_url}/admin/realms/{self.realm}/clients",
            headers=headers,
            json=get_default_client_config(self.audience),
            timeout=30,
        )

        if response.status_code in (201, 409):
            LOG.info("Client '%s' ready", self.audience)
            self._assign_admin_role(admin_token)
        else:
            LOG.warning("Failed to create client: %s", response.text)

    def _assign_admin_role(self, admin_token: str):
        """Assign admin role to service account."""
        base_url = self._get_base_url()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }

        try:
            # Get client UUID
            clients = requests.get(
                f"{base_url}/admin/realms/{self.realm}/clients",
                headers=headers,
                params={"clientId": self.audience},
                timeout=30,
            ).json()
            if not clients:
                return
            client_uuid = clients[0]["id"]

            # Get service account user
            service_account = requests.get(
                f"{base_url}/admin/realms/{self.realm}/clients/{client_uuid}/service-account-user",
                headers=headers,
                timeout=30,
            ).json()

            # Get admin role
            roles = requests.get(
                f"{base_url}/admin/realms/{self.realm}/roles",
                headers=headers,
                timeout=30,
            ).json()
            admin_role = next((r for r in roles if r["name"] == "admin"), None)
            if not admin_role:
                return

            # Assign role
            requests.post(
                f"{base_url}/admin/realms/{self.realm}/users/{service_account['id']}/role-mappings/realm",
                headers=headers,
                json=[admin_role],
                timeout=30,
            )
            LOG.info("Assigned admin role to service account")
        except Exception as e:
            LOG.warning("Failed to assign admin role: %s", e)

    def _create_default_user(self):
        """Create default test user if configured (Keycloak 26+ requires two-step process)."""
        username = get_env(ENV_KEYCLOAK_DEFAULT_USER)
        password = get_env(ENV_KEYCLOAK_DEFAULT_PASSWORD)
        if not username or not password:
            return

        base_url = self._get_base_url()
        headers = {"Authorization": f"Bearer {self._get_admin_token()}"}
        users_url = f"{base_url}/admin/realms/{self.realm}/users"

        try:
            # Create user with required profile fields
            response = requests.post(
                users_url,
                headers=headers,
                json={
                    "username": username,
                    "enabled": True,
                    "emailVerified": True,
                    "email": f"{username}@localstack.local",
                    "firstName": username.capitalize(),
                    "lastName": "User",
                    "requiredActions": [],
                },
                timeout=30,
            )

            if response.status_code == 409:
                return
            if response.status_code != 201:
                LOG.warning("Failed to create user: %s", response.text)
                return

            # Get user ID and set password separately
            users = requests.get(
                users_url, headers=headers, params={"username": username}, timeout=30
            ).json()
            if not users:
                return

            requests.put(
                f"{users_url}/{users[0]['id']}/reset-password",
                headers={**headers, "Content-Type": "application/json"},
                json={"type": "password", "value": password, "temporary": False},
                timeout=30,
            )
            LOG.info("Created user: %s", username)
        except Exception as e:
            LOG.warning("Failed to create user: %s", e)

    def _register_oidc_provider(self):
        """Register Keycloak as OIDC provider in LocalStack IAM."""
        try:
            import boto3
            from botocore.config import Config

            iam = boto3.client(
                "iam",
                endpoint_url=f"http://localhost:{config.get_edge_port_http()}",
                aws_access_key_id="test",
                aws_secret_access_key="test",
                region_name="us-east-1",
                config=Config(signature_version="v4"),
            )

            provider_url = f"keycloak.{constants.LOCALHOST_HOSTNAME}:{config.get_edge_port_http()}/realms/{self.realm}"
            iam.create_open_id_connect_provider(
                Url=f"http://{provider_url}",
                ClientIDList=[self.audience],
                ThumbprintList=["0" * 40],
            )
            LOG.info("Registered OIDC provider: %s", provider_url)
        except Exception as e:
            if "EntityAlreadyExists" not in str(e):
                LOG.warning("Failed to register OIDC provider: %s", e)

    def _log_startup_info(self):
        """Log startup information."""
        port = config.get_edge_port_http()
        keycloak_url = f"http://keycloak.{constants.LOCALHOST_HOSTNAME}:{port}"

        LOG.info("")
        LOG.info("=" * 60)
        LOG.info("Keycloak Extension Started")
        LOG.info("=" * 60)
        LOG.info("Admin Console: http://localhost:8080/admin")
        LOG.info("Credentials:   admin / admin")
        LOG.info(
            "Token URL:     %s/realms/%s/protocol/openid-connect/token",
            keycloak_url,
            self.realm,
        )
        LOG.info("Client:        %s / %s", self.audience, DEFAULT_CLIENT_SECRET)
        LOG.info("=" * 60)
