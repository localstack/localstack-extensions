import logging

from localstack.utils.run import ShellCommandThread
from localstack.utils.serving import Server
from localstack.utils.threads import TMP_THREADS


class HttpbinServer(Server):
    logger = logging.getLogger("httpbin")

    def do_start_thread(self):
        thread = ShellCommandThread(
            [
                "/opt/code/localstack/.venv/bin/python",
                "-m",
                "localstack_httpbin.vendor.httpbin.core",
                "--port",
                str(self.port),
            ],
            log_listener=self._log_listener,
        )
        TMP_THREADS.append(thread)
        thread.start()
        return thread

    def _log_listener(self, line, **_kwargs):
        self.logger.debug(line.rstrip())
