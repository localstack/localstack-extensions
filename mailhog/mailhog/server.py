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

    default_web_path = "mailhog"
    """WebPath under which the UI is served (without leading or trailing slashes)"""

    default_smtp_port = 25
    """Default port used to expose the SMTP server, unless MH_SMTP_BIND_ADDR is set."""

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

    @property
    def ui_port(self) -> int:
        if addr := os.getenv("MH_UI_BIND_ADDR"):
            return int(addr.split(":")[-1])
        return self.port

    @property
    def smtp_port(self) -> int:
        if addr := os.getenv("MH_SMTP_BIND_ADDR"):
            return int(addr.split(":")[-1])

        return self.default_smtp_port

    @property
    def web_path(self):
        """Returns the configured path under which the web UI will be available when using path-based
        routing. This should be without trailing or prefixed slashes. by default, it results in
        http://localhost:4566/mailhog."""
        return os.getenv("MH_UI_WEB_PATH") or self.default_web_path

    def _create_env_vars(self) -> dict:
        """All configuration of mailhog"""
        # pre-populate the relevant variables
        env = {k: v for k, v in os.environ.items() if k.startswith("MH_")}

        # web path is needed to not conflict with the default router
        env["MH_UI_WEB_PATH"] = self.web_path

        # configure persistence unless the user overwrites it
        if config.PERSISTENCE and not os.getenv("MH_STORAGE"):
            env["MH_STORAGE"] = "maildir"
            # pointing it to the asset directory will make persistence work out of the box
            env["MH_MAILDIR_PATH"] = env.get(
                "MH_MAILDIR_PATH", os.path.join(config.dirs.data, "mailhog")
            )

        if not os.getenv("MH_API_BIND_ADDR"):
            env["MH_API_BIND_ADDR"] = f"{self.host}:{self.port}"

        if not os.getenv("MH_UI_BIND_ADDR"):
            env["MH_UI_BIND_ADDR"] = f"{self.host}:{self.ui_port}"

        if not os.getenv("MH_SMTP_BIND_ADDR"):
            env["MH_SMTP_BIND_ADDR"] = f"{self.host}:{self.smtp_port}"

        if not os.getenv("MH_HOSTNAME"):
            # TODO: reconcile with LOCALSTACK_HOST (although this may only be cosmetics for the EHLO command)
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
