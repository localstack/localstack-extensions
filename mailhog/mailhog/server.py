"""
Tools to run the mailhog service.
"""
import logging
import os

from localstack import config
from localstack.utils.net import get_free_tcp_port
from localstack.utils.run import ShellCommandThread
from localstack.utils.serving import Server
from localstack.utils.threads import TMP_THREADS

from mailhog.package import mailhog_package

LOG = logging.getLogger(__name__)


class MailHogServer(Server):

    """
    Mailhog server abstraction. Uses environment-based configuration as described here:
    https://github.com/mailhog/MailHog/blob/master/docs/CONFIG.md.

    It exposes three services:
    * The mailhog API (random port)
    * The mailhog UI (same port as API)
    * The mailhog SMTP server (25)

    It supports snapshot persistence by pointing the MH_MAILDIR_PATH to the asset directory.
    """

    def __init__(self, host: str = "0.0.0.0") -> None:
        super().__init__(self._get_configured_or_random_api_port(), host)

    def do_start_thread(self):
        mailhog_package.install()

        cmd = self._create_command()
        env = self._create_env_vars()

        LOG.debug("starting mailhog thread: %s, %s", cmd, env)

        t = ShellCommandThread(
            cmd,
            env_vars=env,
            name="mailhog",
            log_listener=self._log_listener,
        )
        TMP_THREADS.append(t)
        t.start()
        return t

    def _log_listener(self, line, **_kwargs):
        LOG.debug(line.rstrip())

    def get_ui_port(self) -> int:
        if addr := os.getenv("MH_UI_BIND_ADDR"):
            return int(addr.split(":")[-1])
        return self.port

    def get_smtp_port(self) -> int:
        if addr := os.getenv("MH_SMTP_BIND_ADDR"):
            return int(addr.split(":")[-1])

        # TODO: use random port by default?
        return 25

    def _create_env_vars(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k.startswith("MH_")}

        if not os.getenv("MH_STORAGE") and config.PERSISTENCE:
            env["MH_STORAGE"] = "maildir"
            env["MH_MAILDIR_PATH"] = env.get(
                "MH_MAILDIR_PATH", os.path.join(config.dirs.data, "mailhog")
            )

        if not os.getenv("MH_API_BIND_ADDR"):
            env["MH_API_BIND_ADDR"] = f"{self.host}:{self.port}"

        if not os.getenv("MH_UI_BIND_ADDR"):
            env["MH_UI_BIND_ADDR"] = f"{self.host}:{self.get_ui_port()}"

        if not os.getenv("MH_SMTP_BIND_ADDR"):
            env["MH_SMTP_BIND_ADDR"] = f"{self.host}:{self.get_smtp_port()}"

        if not os.getenv("MH_HOSTNAME"):
            # TODO: reconcile with LOCALSTACK_HOST
            env["MH_HOSTNAME"] = "mailhog.localhost.localstack.cloud"

        return env

    def _create_command(self) -> list[str]:
        cmd = [mailhog_package.get_installer().get_executable_path()]
        return cmd

    @staticmethod
    def _get_configured_or_random_api_port() -> int:
        if addr := os.getenv("MH_API_BIND_ADDR"):
            return int(addr.split(":")[-1])

        return get_free_tcp_port()
