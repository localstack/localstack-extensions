import os
import shlex

from localstack.config import is_env_not_false
from localstack.utils.docker_utils import DOCKER_CLIENT
from localstack_typedb.utils.docker import ProxiedDockerContainerExtension
from rolo import Request
from werkzeug.datastructures import Headers

# environment variable for user-defined command args to pass to TypeDB
ENV_CMD_FLAGS = "TYPEDB_FLAGS"
# environment variable for flag to enable/disable HTTP2 proxy for gRPC traffic
ENV_HTTP2_PROXY = "TYPEDB_HTTP2_PROXY"


class TypeDbExtension(ProxiedDockerContainerExtension):
    name = "typedb"

    # pattern of the hostname under which the extension is accessible
    HOST = "typedb.<domain>"
    # name of the Docker image to spin up
    DOCKER_IMAGE = "typedb/typedb"
    # default command args to pass to TypeDB
    DEFAULT_CMD_FLAGS = ["--diagnostics.reporting.metrics=false"]
    # default port for TypeDB HTTP2/gRPC endpoint
    TYPEDB_PORT = 1729

    def __init__(self):
        command_flags = (os.environ.get(ENV_CMD_FLAGS) or "").strip()
        command_flags = self.DEFAULT_CMD_FLAGS + shlex.split(command_flags)
        http2_ports = [self.TYPEDB_PORT] if is_env_not_false(ENV_HTTP2_PROXY) else []
        super().__init__(
            image_name=self.DOCKER_IMAGE,
            container_ports=[8000, 1729],
            host=self.HOST,
            request_to_port_router=self.request_to_port_router,
            command=command_flags,
            http2_ports=http2_ports,
        )

    def should_proxy_request(self, headers: Headers) -> bool:
        # determine if this is a gRPC request targeting TypeDB
        content_type = headers.get("content-type") or ""
        req_path = headers.get(":path") or ""
        is_typedb_grpc_request = (
            "grpc" in content_type and "/typedb.protocol.TypeDB" in req_path
        )
        return is_typedb_grpc_request

    def request_to_port_router(self, request: Request) -> int:
        # TODO add REST API / gRPC routing based on request
        return 1729
