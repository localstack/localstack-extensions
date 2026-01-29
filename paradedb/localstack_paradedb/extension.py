import os
import logging

from localstack_paradedb.utils.docker import DatabaseDockerContainerExtension

LOG = logging.getLogger(__name__)

# Environment variables for configuration
ENV_POSTGRES_USER = "PARADEDB_POSTGRES_USER"
ENV_POSTGRES_PASSWORD = "PARADEDB_POSTGRES_PASSWORD"
ENV_POSTGRES_DB = "PARADEDB_POSTGRES_DB"
ENV_POSTGRES_PORT = "PARADEDB_POSTGRES_PORT"

# Default values
DEFAULT_POSTGRES_USER = "myuser"
DEFAULT_POSTGRES_PASSWORD = "mypassword"
DEFAULT_POSTGRES_DB = "mydatabase"
DEFAULT_POSTGRES_PORT = 5432


class ParadeDbExtension(DatabaseDockerContainerExtension):
    name = "paradedb"

    # Name of the Docker image to spin up
    DOCKER_IMAGE = "paradedb/paradedb"

    def __init__(self):
        # Get configuration from environment variables
        postgres_user = os.environ.get(ENV_POSTGRES_USER, DEFAULT_POSTGRES_USER)
        postgres_password = os.environ.get(
            ENV_POSTGRES_PASSWORD, DEFAULT_POSTGRES_PASSWORD
        )
        postgres_db = os.environ.get(ENV_POSTGRES_DB, DEFAULT_POSTGRES_DB)
        postgres_port = int(os.environ.get(ENV_POSTGRES_PORT, DEFAULT_POSTGRES_PORT))

        # Environment variables to pass to the container
        env_vars = {
            "POSTGRES_USER": postgres_user,
            "POSTGRES_PASSWORD": postgres_password,
            "POSTGRES_DB": postgres_db,
        }

        super().__init__(
            image_name=self.DOCKER_IMAGE,
            container_ports=[postgres_port],
            env_vars=env_vars,
        )

        # Store configuration for connection info
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password
        self.postgres_db = postgres_db
        self.postgres_port = postgres_port

    def get_connection_info(self) -> dict:
        """Return connection information for ParadeDB."""
        info = super().get_connection_info()
        info.update(
            {
                "database": self.postgres_db,
                "user": self.postgres_user,
                "password": self.postgres_password,
                "port": self.postgres_port,
                "connection_string": (
                    f"postgresql://{self.postgres_user}:{self.postgres_password}"
                    f"@{self.container_host}:{self.postgres_port}/{self.postgres_db}"
                ),
            }
        )
        return info
