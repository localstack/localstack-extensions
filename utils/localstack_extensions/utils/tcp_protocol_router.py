"""
Protocol-detecting TCP router for LocalStack Gateway.

This module provides a Twisted protocol that detects the protocol from initial
connection bytes and routes to the appropriate backend, enabling multiple TCP
protocols to share a single gateway port.
"""

import logging
from twisted.internet import reactor
from twisted.protocols.portforward import ProxyClient, ProxyClientFactory
from twisted.web.http import HTTPChannel

from localstack.utils.patch import patch

LOG = logging.getLogger(__name__)

# Global registry of extensions with TCP matchers
# List of tuples: (extension_name, matcher_func, backend_host, backend_port)
_tcp_extensions = []
_gateway_patched = False


class TcpProxyClient(ProxyClient):
    """Backend TCP connection for protocol-detected connections."""

    def connectionMade(self):
        """Called when backend connection is established."""
        server = self.factory.server

        # Set up peer relationship
        server.set_tcp_peer(self)

        # Enable flow control
        self.transport.registerProducer(server.transport, True)
        server.transport.registerProducer(self.transport, True)

        # Send buffered data from detection phase
        if hasattr(self.factory, "initial_data"):
            initial_data = self.factory.initial_data
            LOG.debug(f"Sending {len(initial_data)} buffered bytes to backend")
            self.transport.write(initial_data)
            del self.factory.initial_data

    def dataReceived(self, data):
        """Forward data from backend to client."""
        self.factory.server.transport.write(data)

    def connectionLost(self, reason):
        """Backend connection closed."""
        self.factory.server.transport.loseConnection()


def patch_gateway_for_tcp_routing():
    """
    Patch the LocalStack gateway to enable protocol detection and TCP routing.

    This monkeypatches the HTTPChannel class used by the gateway to intercept
    connections and detect TCP protocols before HTTP processing.
    """
    global _gateway_patched

    if _gateway_patched:
        LOG.debug("Gateway already patched for TCP routing")
        return

    LOG.debug("Patching LocalStack gateway for TCP protocol detection")
    peek_bytes_length = 32

    # Patch HTTPChannel to use our protocol-detecting version
    @patch(HTTPChannel.__init__)
    def _patched_init(fn, self, *args, **kwargs):
        # Call original init
        fn(self, *args, **kwargs)
        # Add our detection attributes
        self._detection_buffer = []
        self._detecting = True
        self._tcp_peer = None
        self._detection_buffer_size = peek_bytes_length

    @patch(HTTPChannel.dataReceived)
    def _patched_dataReceived(fn, self, data):
        """Intercept data to allow extensions to claim TCP connections."""
        if not getattr(self, "_detecting", False):
            # Already decided - either proxying TCP or processing HTTP
            if getattr(self, "_tcp_peer", None):
                # TCP proxying mode
                self._tcp_peer.transport.write(data)
            else:
                # HTTP mode - pass to original
                fn(self, data)
            return

        # Still detecting - buffer data
        if not hasattr(self, "_detection_buffer"):
            self._detection_buffer = []
        self._detection_buffer.append(data)
        buffered_data = b"".join(self._detection_buffer)

        # Try each registered extension's matcher
        if len(buffered_data) >= 8:
            for ext_name, matcher, backend_host, backend_port in _tcp_extensions:
                try:
                    if matcher(buffered_data):
                        LOG.info(
                            f"Extension {ext_name} claimed connection, routing to "
                            f"{backend_host}:{backend_port}"
                        )
                        # Switch to TCP proxy mode
                        self._detecting = False
                        self.transport.pauseProducing()

                        # Create backend connection
                        client_factory = ProxyClientFactory()
                        client_factory.protocol = TcpProxyClient
                        client_factory.server = self
                        client_factory.initial_data = buffered_data

                        reactor.connectTCP(backend_host, backend_port, client_factory)
                        return
                except Exception as e:
                    LOG.debug(f"Error in matcher for {ext_name}: {e}")
                    continue

            # No extension claimed the connection
            buffer_size = getattr(self, "_detection_buffer_size", peek_bytes_length)
            if len(buffered_data) >= buffer_size:
                LOG.debug("No TCP extension matched, using HTTP handler")
                self._detecting = False
                # Feed buffered data to HTTP handler
                for chunk in self._detection_buffer:
                    fn(self, chunk)
                self._detection_buffer = []

    @patch(HTTPChannel.connectionLost)
    def _patched_connectionLost(fn, self, reason):
        """Handle connection close."""
        tcp_peer = getattr(self, "_tcp_peer", None)
        if tcp_peer:
            tcp_peer.transport.loseConnection()
            self._tcp_peer = None
        fn(self, reason)

    # Monkey-patch the set_tcp_peer method onto HTTPChannel
    def set_tcp_peer(self, peer):
        """Called when backend TCP connection is established."""
        self._tcp_peer = peer
        self.transport.resumeProducing()

    HTTPChannel.set_tcp_peer = set_tcp_peer

    _gateway_patched = True
    LOG.info("Gateway patched successfully for TCP protocol routing")


def register_tcp_extension(
    extension_name: str,
    matcher: callable,
    backend_host: str,
    backend_port: int,
):
    """
    Register an extension for TCP connection routing.

    Args:
        extension_name: Name of the extension
        matcher: Function that takes bytes and returns bool to claim connection
        backend_host: Backend host to route to
        backend_port: Backend port to route to
    """
    _tcp_extensions.append((extension_name, matcher, backend_host, backend_port))
    LOG.info(
        f"Registered TCP extension {extension_name} -> {backend_host}:{backend_port}"
    )


def unregister_tcp_extension(extension_name: str):
    """Unregister an extension from TCP routing."""
    global _tcp_extensions
    _tcp_extensions = [
        (name, matcher, host, port)
        for name, matcher, host, port in _tcp_extensions
        if name != extension_name
    ]
    LOG.info(f"Unregistered TCP extension {extension_name}")
