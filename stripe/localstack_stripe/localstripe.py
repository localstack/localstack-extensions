import logging
import sys
from multiprocessing import Process
from typing import Optional

from localstripe.server import start as start_localstripe

LOG = logging.getLogger(__name__)

_process: Optional[Process] = None


def _serve(port: int):
    sys.argv = [__file__, "--port", str(port)]
    return start_localstripe()


def start(port: int) -> Process:
    global _process
    if _process:
        return _process

    LOG.info("starting localstripe server on port %s", port)
    _process = Process(target=_serve, args=(port,), daemon=True)
    _process.start()
    return _process


def shutdown():
    global _process
    if not _process:
        return
    LOG.info("shutting down localstripe server")

    _process.terminate()
    _process = None
