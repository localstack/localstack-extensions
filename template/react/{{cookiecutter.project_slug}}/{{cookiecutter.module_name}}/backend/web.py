import mimetypes
import os
from pathlib import Path

from flask import redirect
from localstack.constants import (
    APPLICATION_OCTET_STREAM,
    INTERNAL_RESOURCE_PATH,
    LOCALHOST_HOSTNAME,
)
from localstack.http import route, Request, Response

from {{cookiecutter.module_name}} import frontend as web_ui


DOMAIN_NAME = f"{{cookiecutter.module_name}}.{LOCALHOST_HOSTNAME}"
ROUTE_HOST = f"{DOMAIN_NAME}<port:port>"
EXTENSION_SUB_ROUTE = f"{ROUTE_HOST}{INTERNAL_RESOURCE_PATH}/{{cookiecutter.module_name}}"


class WebApp:
    @route("/", methods=["GET"], host=ROUTE_HOST)
    def forward_from_root(self, request: Request, **kwargs):
        return redirect(f"{INTERNAL_RESOURCE_PATH}/{{cookiecutter.module_name}}/dashboard")

    @route("/<path:path>", methods=["GET"], host=ROUTE_HOST)
    def forward_custom_from_root(self, request: Request, path: str, **kwargs):
        return self.serve_static_file(path)
    
    @route(f"{INTERNAL_RESOURCE_PATH}/{{cookiecutter.module_name}}", methods=["GET"])
    def forward_from_extension_root(self, request: Request, **kwargs):
        return redirect(f"{INTERNAL_RESOURCE_PATH}/{{cookiecutter.module_name}}/index.html")

    @route(f"{INTERNAL_RESOURCE_PATH}/{{cookiecutter.module_name}}/<path:path>", methods=["GET"])
    def get_web_asset(self, request: Request, path: str, **kwargs):
        return self.serve_static_file(path)

    @route(f"{INTERNAL_RESOURCE_PATH}/{{cookiecutter.module_name}}/index.html", methods=["GET"])
    def serve_index_html(self, request: Request, **kwargs):
        return self.serve_static_file("index.html")

    def serve_static_file(self, path: str):
        build_dir = os.path.join(os.path.dirname(web_ui.__file__), "build")
        file_path = os.path.join(build_dir, path.lstrip("/"))

        if not os.path.exists(file_path):
            file_path = os.path.join(build_dir, "index.html")

        mime_type = mimetypes.guess_type(file_path)[0] or APPLICATION_OCTET_STREAM

        return Response(Path(file_path).open(mode="rb"), mimetype=mime_type)
