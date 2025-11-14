import logging
import socket
from abc import abstractmethod

from h2.frame_buffer import FrameBuffer
from hpack import Decoder
from hyperframe.frame import HeadersFrame, Frame
from twisted.internet import reactor

from localstack.utils.patch import patch
from twisted.web._http2 import H2Connection
from werkzeug.datastructures import Headers

LOG = logging.getLogger(__name__)


class ProxyRequestMatcher:
    """
    Abstract base class that defines a request matcher, for an extension to define which incoming
    request messages should be proxied to an upstream target (and which ones shouldn't).
    """

    @abstractmethod
    def should_proxy_request(self, headers: Headers) -> bool:
        """Define whether a request should be proxied, based on request headers."""


class TcpForwarder:
    """Simple helper class for bidirectional forwarding of TPC traffic."""

    buffer_size: int = 1024
    """Data buffer size for receiving data from upstream socket."""

    def __init__(self, port: int, host: str = "localhost"):
        self.port = port
        self.host = host
        self._socket = None
        self.connect()

    def connect(self):
        if not self._socket:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.host, self.port))

    def receive_loop(self, callback):
        while True:
            data = self._socket.recv(self.buffer_size)
            callback(data)
            if not data:
                break

    def send(self, data):
        self._socket.sendall(data)

    def close(self):
        LOG.debug("Closing connection to upstream HTTP2 server on port %s", self.port)
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except Exception:
            # swallow exceptions here (e.g., "bad file descriptor")
            pass


def apply_http2_patches_for_grpc_support(
    target_host: str, target_port: int, request_matcher: ProxyRequestMatcher
):
    """
    Apply some patches to proxy incoming gRPC requests and forward them to a target port.
    Note: this is a very brute-force approach and needs to be fixed/enhanced over time!
    """

    @patch(H2Connection.connectionMade)
    def _connectionMade(fn, self, *args, **kwargs):
        def _process(data):
            LOG.debug("Received data (%s bytes) from upstream HTTP2 server", len(data))
            self.transport.write(data)

        # TODO: make port configurable
        self._ls_forwarder = TcpForwarder(target_port, host=target_host)
        LOG.debug(
            "Starting TCP forwarder to port %s for new HTTP2 connection", target_port
        )
        reactor.getThreadPool().callInThread(self._ls_forwarder.receive_loop, _process)

    @patch(H2Connection.dataReceived)
    def _dataReceived(fn, self, data, *args, **kwargs):
        forwarder = getattr(self, "_ls_forwarder", None)
        should_proxy_request = getattr(self, "_ls_should_proxy_request", None)
        if not forwarder or should_proxy_request is False:
            return fn(self, data, *args, **kwargs)

        if should_proxy_request:
            forwarder.send(data)
            return

        setattr(self, "_data_received", getattr(self, "_data_received", []))
        self._data_received.append(data)

        # parse headers from request frames received so far
        headers = get_headers_from_data_stream(self._data_received)
        if not headers:
            # if no headers received yet, then return (method will be called again for next chunk of data)
            return

        # check if the incoming request should be proxies, based on the request headers
        self._ls_should_proxy_request = request_matcher.should_proxy_request(headers)

        if not self._ls_should_proxy_request:
            # if this is not a target request, then call the upstream function
            result = None
            for chunk in self._data_received:
                result = fn(self, chunk, *args, **kwargs)
            self._data_received = []
            return result

        # forward data chunks to the target
        for chunk in self._data_received:
            LOG.debug(
                "Forwarding data (%s bytes) from HTTP2 client to server", len(chunk)
            )
            forwarder.send(chunk)
        self._data_received = []

    @patch(H2Connection.connectionLost)
    def connectionLost(fn, self, *args, **kwargs):
        forwarder = getattr(self, "_ls_forwarder", None)
        if not forwarder:
            return fn(self, *args, **kwargs)
        forwarder.close()


def get_headers_from_data_stream(data_list: list[bytes]) -> Headers:
    """Get headers from a data stream (list of bytes data), if any headers are contained."""
    data_combined = b"".join(data_list)
    frames = parse_http2_stream(data_combined)
    headers = get_headers_from_frames(frames)
    return headers


def get_headers_from_frames(frames: list[Frame]) -> Headers:
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


def parse_http2_stream(data: bytes) -> list[Frame]:
    """Parse the data from an HTTP2 stream into a list of frames"""
    frames = []
    buffer = FrameBuffer(server=True)
    buffer.max_frame_size = 16384
    buffer.add_data(data)
    try:
        for frame in buffer:
            frames.append(frame)
    except Exception:
        pass
    return frames
