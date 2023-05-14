import logging
import os
from typing import Any, Dict

import requests
from localstack import config
from localstack.extensions.api import Extension, http
from localstack.http import Request, Response
from localstack.packages import InstallTarget
from localstack.packages.core import ExecutableInstaller
from localstack.utils.files import load_file, new_tmp_file, save_file
from localstack.utils.net import get_free_tcp_port
from localstack.utils.run import run
from localstack.utils.serving import Server

LOG = logging.getLogger(__name__)

# maps script names to source codes
SCRIPT_CODES = {}
# maps script names to miniflare servers
SCRIPT_SERVERS = {}

# identifier for default version installed by package installer
DEFAULT_VERSION = "latest"


class MiniflareExtension(Extension):
    name = "miniflare"

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from miniflare.config import HANDLER_PATH_MINIFLARE

        LOG.info("miniflare: adding routes to activate extension")
        all_methods = ["GET", "POST", "PUT", "DELETE"]

        def _add_route(path, handler):
            router.add(
                f"{HANDLER_PATH_MINIFLARE}{path}",
                handler,
                methods=all_methods,
            )

        _add_route("/user", handle_user)
        _add_route("/memberships", handle_memberships)
        _add_route(
            "/accounts/<account_id>/workers/scripts/<script_name>", handle_scripts
        )
        _add_route(
            "/accounts/<account_id>/workers/services/<service_name>", handle_services
        )
        _add_route("/accounts/<account_id>/workers/subdomain", handle_subdomain)
        _add_route(
            "/accounts/<account_id>/workers/scripts/<script_name>/subdomain",
            handle_script_subdomain,
        )
        _add_route(
            "/accounts/<account_id>/workers/deployments/by-script/<script_name>",
            handle_deployments,
        )

        router.add(
            "/<path:path>",
            handle_invocation,
            methods=all_methods,
            host="<script_name>.miniflare.localhost.localstack.cloud<regex('(:[0-9]{1,5})?'):port>",
        )


def handle_invocation(request: Request, path: str, script_name: str, port: str):
    LOG.info("Handle invocation of cloudflare worker %s", script_name)
    port = SCRIPT_SERVERS[script_name].port
    response = requests.request(
        method=request.method,
        url=f"http://localhost:{port}{request.path}",
        data=request.get_data(),
    )
    result = Response()
    result.status_code = response.status_code
    result.set_data(response.content)
    result.headers.update(dict(response.headers))
    return result


# TODO: mock implementation of functions below is only a quick first hack - replace with proper logic!


def handle_user(request: Request) -> Dict:
    return _wrap(
        {
            "id": "7c5dae5552338874e5053f2534d2767a",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Appleseed",
            "username": "cfuser12345",
            "telephone": "+1 123-123-1234",
            "country": "US",
            "zipcode": "12345",
            "created_on": "2014-01-01T05:20:00Z",
            "modified_on": "2014-01-01T05:20:00Z",
            "two_factor_authentication_enabled": False,
            "suspended": False,
        }
    )


def handle_memberships(request: Request) -> Dict[str, Any]:
    return _wrap(
        [
            {
                "id": "4536bcfad5faccb111b47003c79917fa",
                "code": "05dd05cce12bbed97c0d87cd78e89bc2fd41a6cee72f27f6fc84af2e45c0fac0",
                "api_access_enabled": True,
                "status": "accepted",
                "account": {
                    "id": "01a7362d577a6c3019a474fd6f485823",
                    "name": "Demo Account",
                    "settings": {
                        "enforce_twofactor": False,
                        "api_access_enabled": None,
                        "use_account_custom_ns_by_default": False,
                    },
                    "created_on": "2014-03-01T12:21:02.0000Z",
                },
                "roles": ["Account Administrator"],
                "permissions": {},
            }
        ]
    )


def handle_scripts(request: Request, account_id: str, script_name: str) -> Dict:
    if request.method == "PUT":
        SCRIPT_CODES[script_name] = files = dict(request.files)
        MiniflareInstaller().install()
        port = get_free_tcp_port()
        script_path = f"{new_tmp_file()}.js"
        # TODO add support for multiple script files!
        if len(files) > 1:
            LOG.warning(
                "Multiple worker scripts uploaded (expected 1): %s", files.keys()
            )
        list(files.values())[0].save(script_path)
        server = MiniflareServer(script_path, port=port)
        server.start()
        SCRIPT_SERVERS[script_name] = server
    return _wrap({})


def handle_services(request: Request, account_id: str, service_name: str) -> Dict:
    return _wrap(
        {
            "default_environment": {
                "script": {
                    "etag": "13a3240e8fb414561b0366813b0b8f42b3e6cfa0d9e70e99835dae83d0d8a794",
                    "handlers": ["fetch"],
                    "last_deployed_from": "api",
                }
            }
        }
    )


def handle_subdomain(request: Request, account_id: str) -> Dict:
    return _wrap({})


def handle_script_subdomain(
    request: Request, account_id: str, script_name: str
) -> Dict:
    return _wrap({})


def handle_deployments(request: Request, account_id: str, script_name: str) -> Dict:
    return _wrap(
        {
            "latest": {
                "id": "bcf48806-b317-4351-9ee7-36e7d557d4de",
                "number": 1,
                "metadata": {
                    "created_on": "2022-11-15T18:25:44.442097Z",
                    "modified_on": "2022-11-15T18:25:44.442097Z",
                    "source": "api",
                    "author_id": "408cbcdfd4dda4617efef40b04d168a1",
                    "author_email": "user@example.com",
                },
                "resources": {
                    "script": {
                        "etag": "13a3240e8fb414561b0366813b0b8f42b3e6cfa0d9e70e99835dae83d0d8a794",
                        "handlers": ["fetch"],
                        "last_deployed_from": "api",
                    },
                    "script_runtime": {"usage_model": "bundled"},
                    "bindings": [
                        {"json": "example_binding", "name": "JSON_VAR", "type": "json"}
                    ],
                },
            },
            "items": [
                {
                    "id": "bcf48806-b317-4351-9ee7-36e7d557d4de",
                    "number": 1,
                    "metadata": {
                        "created_on": "2022-11-15T18:25:44.442097Z",
                        "modified_on": "2022-11-15T18:25:44.442097Z",
                        "source": "api",
                        "author_id": "408cbcdfd4dda4617efef40b04d168a1",
                        "author_email": "user@example.com",
                    },
                }
            ],
        }
    )


def _wrap(result):
    if "result" not in result:
        result = {"result": result}
    return {"success": True, "errors": [], "messages": [], **result}


class MiniflareServer(Server):
    def __init__(self, script_path, port):
        self.script_path = script_path
        super().__init__(port)

    def do_run(self):
        root_dir = os.path.join(config.dirs.var_libs, "miniflare", DEFAULT_VERSION)
        wranger_bin = os.path.join(root_dir, "node_modules", ".bin", "wrangler")

        cmd = [
            wranger_bin,
            "dev",
            "--experimental-local",
            "--port",
            str(self.port),
            self.script_path,
        ]
        LOG.info("Running command: %s", cmd)
        # setting CI=1, to force non-interactive mode of wrangler script
        env_vars = {"CI": "1"}
        run(cmd, env_vars=env_vars, cwd=root_dir)


class MiniflareInstaller(ExecutableInstaller):
    def __init__(self):
        super().__init__("miniflare", version=DEFAULT_VERSION)

    def _get_install_marker_path(self, install_dir: str) -> str:
        # force re-install on every start (requires npm package + system libs like libc++)
        return os.path.join(install_dir, "__invalid_file_path__")

    def _install(self, target: InstallTarget) -> None:
        target_dir = self._get_install_dir(target)

        # note: latest version of miniflare/workerd requires libc++ dev libs
        sources_list_file = "/etc/apt/sources.list"
        sources_list = load_file(sources_list_file)
        sources_list += "\ndeb https://deb.debian.org/debian testing main contrib"
        save_file(sources_list_file, sources_list)
        run(["apt", "update"])

        # bit tricky to get around the libcrypt1.so install issue, see:
        #   https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=993755
        cmd = "cd /tmp; apt -y download libcrypt1 && dpkg-deb -x libcrypt1*.deb . && cp /tmp/lib/*/libcrypt.so.1 /lib/"
        run(["bash", "-c", cmd])
        run(["apt", "install", "-y", "libc++-dev"])
        run(["npm", "i", "-g", "patch-package"])

        # install npm package
        run(["npm", "install", "--prefix", target_dir, "wrangler"])
        run(["npm", "install", "--prefix", target_dir, "@miniflare/tre"])
