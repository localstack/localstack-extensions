import logging
import socket
from enum import Enum
from typing import Iterable, Callable

from h2.frame_buffer import FrameBuffer
from hpack import Decoder
from hyperframe.frame import HeadersFrame, Frame
from twisted.internet import reactor

from localstack.utils.patch import patch
from twisted.web._http2 import H2Connection
from werkzeug.datastructures import Headers

LOG = logging.getLogger(__name__)


ProxyRequestMatcher = Callable[[Headers], bool]


class TcpForwarder:
    """Simple helper class for bidirectional forwarding of TCP traffic."""

    buffer_size: int = 1024
    """Data buffer size for receiving data from upstream socket."""

    def __init__(self, port: int, host: str = "localhost"):
        self.port = port
        self.host = host
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self.host, self.port))
        self._closed = False

    def receive_loop(self, callback):
        while data := self.recv(self.buffer_size):
            callback(data)

    def recv(self, length):
        try:
            return self._socket.recv(length)
        except OSError as e:
            if self._closed:
                return None
            else:
                raise e

    def send(self, data):
        self._socket.sendall(data)

    def close(self):
        if self._closed:
            return
        LOG.debug(f"Closing connection to upstream HTTP2 server on port {self.port}")
        self._closed = True
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except Exception:
            # swallow exceptions here (e.g., "bad file descriptor")
            pass


patched_connection = False


def apply_http2_patches_for_grpc_support(
    target_host: str, target_port: int, should_proxy_request: ProxyRequestMatcher
):
    """
    Apply some patches to proxy incoming gRPC requests and forward them to a target port.
    Note: this is a very brute-force approach and needs to be fixed/enhanced over time!
    """
    LOG.debug(f"Enabling proxying to backend {target_host}:{target_port}")
    global patched_connection
    assert not patched_connection, (
        "It is not safe to patch H2Connection twice with this function"
    )
    patched_connection = True

    class ForwardingState(Enum):
        UNDECIDED = "undecided"
        FORWARDING = "forwarding"
        PASSTHROUGH = "passthrough"

    class ForwardingBuffer:
        """
        A buffer atop the HTTP2 client connection, that will hold
        data until the ProxyRequestMatcher tells us whether to send it
        to the backend, or leave it to the default handler.
        """

        backend: TcpForwarder
        buffer: list
        state: ForwardingState

        def __init__(self, http_response_stream):
            self.http_response_stream = http_response_stream
            LOG.debug(
                f"Starting TCP forwarder to port {target_port} for new HTTP2 connection"
            )
            self.backend = TcpForwarder(target_port, host=target_host)
            self.buffer = []
            self.state = ForwardingState.UNDECIDED
            reactor.getThreadPool().callInThread(
                self.backend.receive_loop, self.received_from_backend
            )

        def received_from_backend(self, data):
            self.http_response_stream.write(data)

        def received_from_http2_client(self, data, default_handler: Callable):
            match self.state:
                case ForwardingState.PASSTHROUGH:
                    default_handler(data)
                case ForwardingState.FORWARDING:
                    assert not self.buffer
                    # Keep sending data to the backend for the lifetime of this connection
                    self.backend.send(data)
                case ForwardingState.UNDECIDED:
                    self.buffer.append(data)

                    if headers := get_headers_from_data_stream(self.buffer):
                        buffered_data = b"".join(self.buffer)
                        self.buffer = []

                        if should_proxy_request(headers):
                            self.state = ForwardingState.FORWARDING
                            self.backend.send(buffered_data)
                        else:
                            self.state = ForwardingState.PASSTHROUGH
                            # if this is not a target request, then call the default handler
                            default_handler(buffered_data)

        def close(self):
            self.backend.close()

    @patch(H2Connection.connectionMade)
    def _connectionMade(fn, self, *args, **kwargs):
        self._ls_forwarding_buffer = ForwardingBuffer(self.transport)

    @patch(H2Connection.dataReceived)
    def _dataReceived(fn, self, data, *args, **kwargs):
        self._ls_forwarding_buffer.received_from_http2_client(
            data, lambda d: fn(self, d, *args, **kwargs)
        )

    @patch(H2Connection.connectionLost)
    def connectionLost(fn, self, *args, **kwargs):
        self._ls_forwarding_buffer.close()


def get_headers_from_data_stream(data_list: Iterable[bytes]) -> Headers:
    """Get headers from a data stream (list of bytes data), if any headers are contained."""
    stream = b"".join(data_list)
    return get_headers_from_frames(get_frames_from_http2_stream(stream))


def get_headers_from_frames(frames: Iterable[Frame]) -> Headers:
    """Parse the given list of HTTP2 frames and return a dict of headers, if any"""
    result = {}
    decoder = Decoder()
    for frame in frames:
        if isinstance(frame, HeadersFrame):
            try:
                headers = decoder.decode(frame.data)
                result.update(dict(headers))
            except Exception:
                pass
    return Headers(result)


def get_frames_from_http2_stream(data: bytes) -> Iterable[Frame]:
    """Parse the data from an HTTP2 stream into an iterable of frames"""
    buffer = FrameBuffer(server=True)
    buffer.max_frame_size = 16384
    try:
        buffer.add_data(data)
        for frame in buffer:
            yield frame
    except Exception:
        pass
