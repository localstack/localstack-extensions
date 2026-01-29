"""
Unit tests for TcpForwarder with mocked sockets.

These tests verify the TcpForwarder class behavior using mocked
socket objects, without requiring actual network connections.
"""

import socket
from unittest.mock import Mock, MagicMock, patch
import pytest

from localstack_extensions.utils.h2_proxy import TcpForwarder


class TestTcpForwarderConstruction:
    """Tests for TcpForwarder initialization."""

    @patch("socket.socket")
    def test_creates_socket_on_init(self, mock_socket_class):
        """Test that TcpForwarder creates a socket on initialization."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=9000, host="example.com")

        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_socket.connect.assert_called_once_with(("example.com", 9000))
        assert forwarder.port == 9000
        assert forwarder.host == "example.com"

    @patch("socket.socket")
    def test_default_host_is_localhost(self, mock_socket_class):
        """Test that default host is localhost."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=8080)

        mock_socket.connect.assert_called_once_with(("localhost", 8080))
        assert forwarder.host == "localhost"

    @patch("socket.socket")
    def test_buffer_size_default(self, mock_socket_class):
        """Test that buffer_size has a default value."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=9000)

        assert forwarder.buffer_size == 1024


class TestTcpForwarderSend:
    """Tests for TcpForwarder.send() method."""

    @patch("socket.socket")
    def test_send_calls_sendall(self, mock_socket_class):
        """Test that send() calls socket.sendall()."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=9000)
        test_data = b"hello world"
        forwarder.send(test_data)

        mock_socket.sendall.assert_called_once_with(test_data)

    @patch("socket.socket")
    def test_send_empty_data(self, mock_socket_class):
        """Test sending empty data."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=9000)
        forwarder.send(b"")

        mock_socket.sendall.assert_called_once_with(b"")

    @patch("socket.socket")
    def test_send_large_data(self, mock_socket_class):
        """Test sending large data."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=9000)
        large_data = b"x" * 100000
        forwarder.send(large_data)

        mock_socket.sendall.assert_called_once_with(large_data)


class TestTcpForwarderReceiveLoop:
    """Tests for TcpForwarder.receive_loop() method."""

    @patch("socket.socket")
    def test_receive_loop_calls_callback(self, mock_socket_class):
        """Test that receive_loop calls callback with received data."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Simulate receiving two chunks then connection close
        mock_socket.recv.side_effect = [b"chunk1", b"chunk2", b""]

        forwarder = TcpForwarder(port=9000)
        callback = Mock()
        forwarder.receive_loop(callback)

        assert callback.call_count == 2
        callback.assert_any_call(b"chunk1")
        callback.assert_any_call(b"chunk2")

    @patch("socket.socket")
    def test_receive_loop_uses_buffer_size(self, mock_socket_class):
        """Test that receive_loop uses the configured buffer size."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        mock_socket.recv.side_effect = [b"data", b""]

        forwarder = TcpForwarder(port=9000)
        forwarder.buffer_size = 2048
        callback = Mock()
        forwarder.receive_loop(callback)

        # recv should be called with buffer_size
        mock_socket.recv.assert_any_call(2048)

    @patch("socket.socket")
    def test_receive_loop_exits_on_empty_data(self, mock_socket_class):
        """Test that receive_loop exits when recv returns empty bytes."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        mock_socket.recv.side_effect = [b""]  # Immediate connection close

        forwarder = TcpForwarder(port=9000)
        callback = Mock()
        forwarder.receive_loop(callback)

        callback.assert_not_called()


class TestTcpForwarderClose:
    """Tests for TcpForwarder.close() method."""

    @patch("socket.socket")
    def test_close_shuts_down_and_closes_socket(self, mock_socket_class):
        """Test that close() properly shuts down and closes the socket."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=9000)
        forwarder.close()

        mock_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        mock_socket.close.assert_called_once()

    @patch("socket.socket")
    def test_close_handles_shutdown_exception(self, mock_socket_class):
        """Test that close() swallows exceptions during shutdown."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        mock_socket.shutdown.side_effect = OSError("Bad file descriptor")

        forwarder = TcpForwarder(port=9000)
        # Should not raise
        forwarder.close()

    @patch("socket.socket")
    def test_close_handles_close_exception(self, mock_socket_class):
        """Test that close() swallows exceptions during close."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        mock_socket.close.side_effect = OSError("Already closed")

        forwarder = TcpForwarder(port=9000)
        # Should not raise
        forwarder.close()

    @patch("socket.socket")
    def test_close_can_be_called_multiple_times(self, mock_socket_class):
        """Test that close() can be called multiple times without error."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        # Second close attempt raises
        mock_socket.shutdown.side_effect = [None, OSError("Already closed")]

        forwarder = TcpForwarder(port=9000)
        forwarder.close()
        forwarder.close()  # Should not raise


class TestTcpForwarderIntegration:
    """Integration-style tests with mocked sockets simulating real behavior."""

    @patch("socket.socket")
    def test_bidirectional_communication(self, mock_socket_class):
        """Test bidirectional send/receive communication pattern."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        forwarder = TcpForwarder(port=9000, host="backend.local")

        # Send some data
        forwarder.send(b"request data")
        mock_socket.sendall.assert_called_with(b"request data")

        # Set up receive
        mock_socket.recv.side_effect = [b"response data", b""]
        received_data = []
        forwarder.receive_loop(lambda data: received_data.append(data))

        assert received_data == [b"response data"]

    @patch("socket.socket")
    def test_http2_preface_send(self, mock_socket_class):
        """Test sending HTTP/2 connection preface."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        HTTP2_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

        forwarder = TcpForwarder(port=9000)
        forwarder.send(HTTP2_PREFACE)

        mock_socket.sendall.assert_called_with(HTTP2_PREFACE)

    @patch("socket.socket")
    def test_connection_refused_on_init(self, mock_socket_class):
        """Test behavior when connection is refused."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        mock_socket.connect.side_effect = ConnectionRefusedError("Connection refused")

        with pytest.raises(ConnectionRefusedError):
            TcpForwarder(port=9000)
