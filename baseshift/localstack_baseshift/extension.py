import logging
import os
import re
import socket
import threading
from dataclasses import dataclass, field

from localstack import config
from localstack.extensions.api import Extension, http
from localstack.http import Request, Response, route
from localstack.utils.container_utils.container_client import (
    NoSuchImage,
    PortMappings,
)
from localstack.utils.docker_utils import DOCKER_CLIENT
from localstack.utils.net import get_addressable_container_host
from localstack.utils.sync import retry
from localstack_extensions.utils.tcp_protocol_router import (
    patch_gateway_for_tcp_routing,
    register_tcp_extension,
    unregister_tcp_extension,
)
from rolo.routing import RuleAdapter, WithHost

LOG = logging.getLogger(__name__)

# Image of the Baseshift clone (Docker snapshot) to start when LocalStack is ready, e.g.
# "<account>.dkr.ecr.<region>.amazonaws.com/<repo>:latest", or an image in the LocalStack ECR registry
ENV_BASESHIFT_IMAGE = "BASESHIFT_IMAGE"
# Database engine of the clone: "postgres" (default) or "mysql"
ENV_BASESHIFT_DB_TYPE = "BASESHIFT_DB_TYPE"
# Encryption password defined when the Dub was created (passed to clones as PASSWORD)
ENV_BASESHIFT_ENCRYPTION_PASSWORD = "BASESHIFT_ENCRYPTION_PASSWORD"
# Any variable with this prefix is passed to the clone containers with the prefix stripped,
# e.g. BASESHIFT_CLONE_BACKUP_SCHEDULE -> BACKUP_SCHEDULE
ENV_CLONE_PREFIX = "BASESHIFT_CLONE_"

API_HOST = "baseshift.<domain>"
DEFAULT_CLONE_NAME = "default"
DB_PORTS = {"postgres": 5432, "mysql": 3306}
# host ports for additional clones, if the default port of the engine is already taken
EXTRA_PORT_RANGE = range(15432, 15532)
CLONE_NAME_REGEX = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$")
# clones may need a while to start up from the snapshot
STARTUP_RETRIES = 120
STARTUP_SLEEP = 2


def is_postgres_handshake(data: bytes) -> bool:
    """
    Identify PostgreSQL connections by protocol handshake: the first message is either
    an SSL request (code 80877103) or a startup message with protocol version 3.0.
    """
    if len(data) < 8:
        return False
    return data[4:8] in (b"\x04\xd2\x16\x2f", b"\x00\x03\x00\x00")


@dataclass
class Clone:
    name: str
    image: str
    db_type: str
    port: int
    env_vars: dict[str, str] = field(default_factory=dict)
    status: str = "starting"
    error: str | None = None

    @property
    def container_name(self) -> str:
        return f"ls-baseshift-clone-{self.name}"

    @property
    def gateway_routed(self) -> bool:
        # only PostgreSQL can be detected on the shared gateway port (MySQL is a server-first
        # protocol), and only the clone on the default port is routed through the gateway
        return self.db_type == "postgres" and self.port == DB_PORTS["postgres"]

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "image": self.image,
            "dbType": self.db_type,
            "status": self.status,
            "hostPort": self.port,
            "endpoints": [f"localhost:{self.port}"],
        }
        if self.gateway_routed:
            # the gateway endpoint as seen by clients (e.g., a custom port configured via LOCALSTACK_HOST)
            result["endpoints"].insert(0, config.LOCALSTACK_HOST.host_and_port())
        if self.error:
            result["error"] = self.error
        return result


class ClonesApi:
    """
    HTTP API to manage clones, similar to the `baseshift server-clone` CLI commands.
    Note: handlers receive the matched host placeholders (e.g., `domain`) as keyword arguments.
    """

    def __init__(self, extension: "BaseshiftExtension"):
        self.extension = extension

    @route("/clones", methods=["GET"])
    def list_clones(self, request: Request, **kwargs):
        return {"clones": [clone.to_dict() for clone in self.extension.list_clones()]}

    @route("/clones", methods=["POST"])
    def create_clone(self, request: Request, **kwargs):
        try:
            payload = request.get_json(force=True) or {}
            clone = self.extension.start_clone(
                name=payload.get("name", ""),
                image=payload.get("image", ""),
                db_type=payload.get("dbType", "postgres"),
                env_vars=payload.get("env") or {},
            )
        except ValueError as e:
            return Response.for_json({"error": str(e)}, status=400)
        except KeyError as e:
            return Response.for_json({"error": str(e.args[0])}, status=409)
        return Response.for_json(clone.to_dict(), status=202)

    @route("/clones/<name>", methods=["GET"])
    def get_clone(self, request: Request, name: str, **kwargs):
        if clone := self.extension.get_clone(name):
            return clone.to_dict()
        return Response.for_json({"error": f"Clone {name} not found"}, status=404)

    @route("/clones/<name>", methods=["DELETE"])
    def delete_clone(self, request: Request, name: str, **kwargs):
        if self.extension.stop_clone(name):
            return Response(status=204)
        return Response.for_json({"error": f"Clone {name} not found"}, status=404)


class BaseshiftExtension(Extension):
    name = "localstack-baseshift"

    def __init__(self):
        self.default_image = os.getenv(ENV_BASESHIFT_IMAGE, "").strip()
        self.default_db_type = self._validate_db_type(
            os.getenv(ENV_BASESHIFT_DB_TYPE, "postgres")
        )
        self.base_env_vars = {
            key.removeprefix(ENV_CLONE_PREFIX): value
            for key, value in os.environ.items()
            if key.startswith(ENV_CLONE_PREFIX) and key != ENV_CLONE_PREFIX
        }
        if password := os.getenv(ENV_BASESHIFT_ENCRYPTION_PASSWORD):
            self.base_env_vars["PASSWORD"] = password
        self.container_host = get_addressable_container_host()
        self._clones: dict[str, Clone] = {}
        self._lock = threading.RLock()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        router.add(WithHost(API_HOST, [RuleAdapter(ClonesApi(self))]))
        patch_gateway_for_tcp_routing()

    def on_platform_ready(self):
        url = f"http://baseshift.{config.LOCALSTACK_HOST.host_and_port()}/clones"
        if not self.default_image:
            LOG.info(
                "Baseshift extension ready. %s is not set - start clones via the API: %s",
                ENV_BASESHIFT_IMAGE,
                url,
            )
            return
        # start the clone after LocalStack is ready - the image may be served by the LocalStack ECR registry
        self.start_clone(DEFAULT_CLONE_NAME, self.default_image, self.default_db_type)
        LOG.info(
            "Baseshift extension ready, starting default clone. Manage clones via: %s",
            url,
        )

    def on_platform_shutdown(self):
        for clone in self.list_clones():
            self._remove_container(clone)

    # clone management

    def list_clones(self) -> list[Clone]:
        with self._lock:
            return list(self._clones.values())

    def get_clone(self, name: str) -> Clone | None:
        with self._lock:
            return self._clones.get(name)

    def start_clone(
        self,
        name: str,
        image: str,
        db_type: str = "postgres",
        env_vars: dict | None = None,
    ) -> Clone:
        if not CLONE_NAME_REGEX.match(name or ""):
            raise ValueError(
                "Clone name must consist of lowercase letters, digits, and dashes (max. 40 chars)"
            )
        if not image:
            raise ValueError("Clone image must be specified")
        db_type = self._validate_db_type(db_type)
        with self._lock:
            if name in self._clones:
                raise KeyError(f"Clone {name} already exists")
            clone = Clone(
                name=name,
                image=image,
                db_type=db_type,
                port=self._allocate_port(db_type),
                env_vars={
                    **self.base_env_vars,
                    **{k: str(v) for k, v in env_vars.items()},
                }
                if env_vars
                else dict(self.base_env_vars),
            )
            self._clones[name] = clone
        threading.Thread(target=self._run_clone, args=(clone,), daemon=True).start()
        return clone

    def stop_clone(self, name: str) -> bool:
        with self._lock:
            clone = self._clones.pop(name, None)
        if not clone:
            return False
        self._remove_container(clone)
        return True

    def _run_clone(self, clone: Clone):
        try:
            self._pull_image(clone.image)
            ports = PortMappings()
            ports.add(clone.port, DB_PORTS[clone.db_type])
            DOCKER_CLIENT.run_container(
                clone.image,
                name=clone.container_name,
                detach=True,
                remove=True,
                ports=ports,
                env_vars=clone.env_vars or None,
            )

            def _check_port():
                with socket.create_connection(
                    (self.container_host, clone.port), timeout=2
                ):
                    pass

            retry(_check_port, retries=STARTUP_RETRIES, sleep=STARTUP_SLEEP)
            if clone.gateway_routed:
                register_tcp_extension(
                    extension_name=self._tcp_route_name(clone),
                    matcher=is_postgres_handshake,
                    backend_host=self.container_host,
                    backend_port=clone.port,
                )
            clone.status = "running"
            LOG.info(
                "Baseshift clone %s is running: %s",
                clone.name,
                clone.to_dict()["endpoints"],
            )
        except Exception as e:
            LOG.warning("Failed to start Baseshift clone %s: %s", clone.name, e)
            clone.status = "failed"
            clone.error = str(e)
            self._remove_container(clone)

    def _pull_image(self, image: str):
        try:
            DOCKER_CLIENT.inspect_image(image, pull=False)
        except NoSuchImage:
            LOG.info("Pulling Baseshift clone image %s", image)
            DOCKER_CLIENT.pull_image(image)

    def _remove_container(self, clone: Clone):
        if clone.gateway_routed:
            unregister_tcp_extension(self._tcp_route_name(clone))
        DOCKER_CLIENT.remove_container(
            clone.container_name, force=True, check_existence=False
        )

    def _allocate_port(self, db_type: str) -> int:
        used_ports = {clone.port for clone in self._clones.values()}
        for port in [DB_PORTS[db_type], *EXTRA_PORT_RANGE]:
            if port not in used_ports:
                return port
        raise ValueError("No free port available for another clone")

    def _tcp_route_name(self, clone: Clone) -> str:
        return f"{self.name}-{clone.name}"

    @staticmethod
    def _validate_db_type(db_type: str) -> str:
        db_type = (db_type or "").strip().lower()
        if db_type not in DB_PORTS:
            raise ValueError(
                f"Database type must be one of {sorted(DB_PORTS)}, got: {db_type}"
            )
        return db_type
