import copy
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import requests
from localstack.http import Request, Response
from localstack.utils.files import new_tmp_file
from localstack.utils.net import get_free_tcp_port

LOG = logging.getLogger(__name__)


@dataclass
class WorkerScript:
    script_path: str
    bindings: dict[str, str]


@dataclass
class Account:
    # maps service names to service details
    services: dict[str, dict] = field(default_factory=dict)
    # maps service names to script details
    scripts: dict[str, WorkerScript] = field(default_factory=dict)
    # maps secret names to values
    secrets: dict[str, dict] = field(default_factory=dict)


class State:
    # maps account ID to account details
    accounts: dict[str, Account] = {}


# maps script names to miniflare servers - TODO use different key name
SCRIPT_SERVERS = {}


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


def handle_user(request: Request) -> dict:
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


def handle_memberships(request: Request) -> dict[str, Any]:
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


def handle_scripts(request: Request, account_id: str, script_name: str) -> dict:
    from miniflare.extension import MiniflareInstaller, MiniflareServer

    account = State.accounts.setdefault(account_id, Account())

    if request.method == "PUT":
        files = dict(request.files)
        MiniflareInstaller().install()
        port = get_free_tcp_port()
        script_path = f"{new_tmp_file()}.js"
        # TODO add support for multiple script files!
        if len(files) > 1:
            LOG.warning(
                "Multiple worker scripts uploaded (expected 1): %s", files.keys()
            )
        list(files.values())[0].save(script_path)

        # get script bindings
        metadata = request.form.get("metadata") or "{}"
        metadata = json.loads(metadata)
        bindings = {bd["name"]: bd.get("text") for bd in metadata.get("bindings", [])}

        account.scripts[script_name] = script = WorkerScript(
            script_path=script_path, bindings=bindings
        )

        # add secrets to script bindings, then execute script
        script = copy.deepcopy(script)
        script.bindings.update(account.secrets.get(script_name) or {})

        existing_server = SCRIPT_SERVERS.get(script_name)
        if existing_server:
            existing_server.shutdown()

        # start new server
        server = MiniflareServer(script, port=port)
        server.start()
        SCRIPT_SERVERS[script_name] = server

    return _wrap({})


def handle_services(request: Request, account_id: str, service_name: str) -> dict:
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


def handle_subdomain(request: Request, account_id: str) -> dict:
    return _wrap({})


def handle_script_subdomain(
    request: Request, account_id: str, script_name: str
) -> dict:
    return _wrap({})


def handle_deployments(request: Request, account_id: str, script_name: str) -> dict:
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


def handle_secrets(request: Request, account_id: str, script_name: str) -> dict:
    account = State.accounts.setdefault(account_id, Account())

    if request.method == "PUT":
        new_vars = request.json
        new_vars = {new_vars["name"]: new_vars.get("text")}
        account.secrets.setdefault(script_name, {}).update(new_vars)

    return _wrap({})


def _wrap(result: dict | list, success: bool = True) -> dict:
    if isinstance(result, list) or "result" not in result:
        result = {"result": result}
    return {"success": success, "errors": [], "messages": [], **result}
