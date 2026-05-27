import json
import logging
import os

from localstack import config
from localstack.extensions.api import Extension, http
from localstack.packages import InstallTarget
from localstack.packages.core import ExecutableInstaller
from localstack.utils.files import load_file, save_file
from localstack.utils.run import run
from localstack.utils.serving import Server

from miniflare.cloudflare_api import (
    WorkerScript,
    handle_deployments,
    handle_invocation,
    handle_memberships,
    handle_script_subdomain,
    handle_scripts,
    handle_secrets,
    handle_services,
    handle_standard,
    handle_subdomain,
    handle_user,
)

LOG = logging.getLogger(__name__)

# Identifier for default version of `wrangler` installed by package installer.
# Note: Currently pinned to 3.1.0, as newer versions make the invocations hang in the LS container
WRANGLER_VERSION = "3.1.0"


def _patch_tls_disable_http2():
    """
    Monkey-patch LocalStack's Twisted gateway to stop advertising HTTP/2 (h2) via ALPN,
    so that all HTTPS connections always negotiate HTTP/1.1.

    ROOT CAUSE
    ----------
    twisted.web.server.Site.acceptableProtocols() returns [b"h2", b"http/1.1"] whenever the
    `h2` Python package is installed (H2_ENABLED = True in twisted.web.http). LocalStack's
    TwistedGateway inherits from Site, so it also advertises h2.

    During TLS connection setup, TLSMemoryBIOFactory._createConnection() calls
    _applyProtocolNegotiation(), which reads wrappedFactory.acceptableProtocols() and
    installs an ALPN select callback that prefers the first listed protocol. Because h2 is
    first, any TLS client that sends h2 in its ALPN extension (modern browsers, Node.js
    fetch/undici, httpx with http2=True, etc.) will have h2 selected.

    After ALPN selects h2, Twisted's _GenericHTTPChannelProtocol.dataReceived() detects
    `negotiatedProtocol == b"h2"` and swaps the underlying channel for an H2Connection
    (twisted.web.http2.H2Connection). H2Connection handles raw HTTP/2 frames and produces
    Request objects via Site.requestFactory, but LocalStack's gateway pipeline is built
    around rolo's WsgiGateway → WSGI environ → LocalstackAwsGateway. The H2Connection
    request/response lifecycle (streams, flow control, DATA frames) is incompatible with
    WSGI, so HTTP/2 requests are processed incorrectly.

    The symptom is that HTTPS requests to extension paths (e.g. /miniflare/user) appear
    to return NoSuchBucket from S3 or are silently dropped, because the garbled HTTP/2
    frames fail to match any registered route and fall through to the legacy_s3_rules
    catch-all in localstack-core/localstack/aws/protocol/service_router.py:
        if method in ["GET", "HEAD"] and stripped:
            return ServiceModelIdentifier("s3")  # incredibly greedy fallback

    HOW THIS PATCH FIXES IT
    -----------------------
    We override TwistedGateway.acceptableProtocols() to return only [b"http/1.1"].
    This propagates through _applyProtocolNegotiation() so the ALPN select callback
    never picks h2. Clients then use HTTP/1.1 over TLS, which works correctly end-to-end
    with LocalStack's WSGI-based gateway.

    TODO: remove this patch once HTTP/2 is properly supported in LocalStack's Twisted
    serving stack. The fix belongs upstream in rolo (TwistedGateway) or localstack-core
    (TLSMultiplexer / TwistedRuntimeServer). Proper HTTP/2 support would require
    integrating H2Connection's stream-based request lifecycle with rolo's gateway model,
    likely via an ASGI-style adapter rather than WSGI.
    See: https://github.com/localstack/localstack-extensions/issues (track upstream fix here)
    """
    try:
        from rolo.serving.twisted import TwistedGateway

        if getattr(TwistedGateway, "_http2_disabled_by_patch", False):
            return

        def _http11_only_protocols(self):
            return [b"http/1.1"]

        TwistedGateway.acceptableProtocols = _http11_only_protocols
        TwistedGateway._http2_disabled_by_patch = True
        LOG.debug("Applied TLS ALPN patch: disabled h2 advertisement for HTTPS connections")
    except Exception as e:
        LOG.warning("Could not apply TLS ALPN patch for HTTPS routing fix: %s", e)


class MiniflareExtension(Extension):
    name = "miniflare"

    def on_extension_load(self):
        _patch_tls_disable_http2()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from miniflare.config import HANDLER_PATH_MINIFLARE

        logging.getLogger("miniflare").setLevel(
            logging.DEBUG if config.DEBUG else logging.INFO
        )

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
        _add_route("/accounts/<account_id>/workers/standard", handle_standard)
        _add_route(
            "/accounts/<account_id>/workers/scripts/<script_name>/subdomain",
            handle_script_subdomain,
        )
        _add_route(
            "/accounts/<account_id>/workers/deployments/by-script/<script_name>",
            handle_deployments,
        )
        _add_route(
            "/accounts/<account_id>/workers/scripts/<script_name>/secrets",
            handle_secrets,
        )

        router.add(
            "/<path:path>",
            handle_invocation,
            methods=all_methods,
            host="<script_name>.miniflare.localhost.localstack.cloud<regex('(:[0-9]{1,5})?'):port>",
        )


class MiniflareServer(Server):
    def __init__(self, script: WorkerScript, port: int):
        self.script = script
        super().__init__(port)

    def do_run(self):
        root_dir = os.path.join(config.dirs.var_libs, "miniflare", WRANGLER_VERSION)
        wrangler_bin = os.path.join(root_dir, "node_modules", ".bin", "wrangler")

        # add global aliases, and variable bindings
        preamble = "globalThis.global = globalThis;\n"
        preamble += "globalThis.window = globalThis;\n"
        preamble += "var global = {};\n"
        for key, value in self.script.bindings.items():
            preamble += f"var {key} = {json.dumps(str(value))};\n"

        # write final script content to file
        script_content = load_file(self.script.script_path)
        script_content = preamble + "\n" + script_content
        script_path_final = f"{self.script.script_path}.final.js"
        save_file(script_path_final, script_content)

        cmd = [
            wrangler_bin,
            "dev",
            "--port",
            str(self.port),
            script_path_final,
        ]
        LOG.info("Running command: %s", cmd)
        # setting CI=1, to force non-interactive mode of wrangler script
        env_vars = {"CI": "1"}
        run(cmd, env_vars=env_vars, cwd=root_dir)


class MiniflareInstaller(ExecutableInstaller):
    def __init__(self):
        super().__init__("miniflare", version=WRANGLER_VERSION)

    def _get_install_marker_path(self, install_dir: str) -> str:
        # force re-install on every start (requires npm package + system libs like libc++)
        return os.path.join(install_dir, "__invalid_file_path__")

    def _install(self, target: InstallTarget) -> None:
        target_dir = self._get_install_dir(target)

        # note: latest version of miniflare/workerd requires libc++ dev libs
        if config.is_in_docker:
            sources_list_file = "/etc/apt/sources.list"
            sources_list = load_file(sources_list_file) or ""
            sources_list += "\ndeb https://deb.debian.org/debian testing main contrib"
            save_file(sources_list_file, sources_list)
            run(["apt", "update"])
            run(["apt", "install", "-y", "libc++-dev"])

        # install npm package
        run(["npm", "install", "--prefix", target_dir, f"wrangler@{WRANGLER_VERSION}"])
