"""
Integration tests for HTTP/2 proxy utilities against a live server.

These tests verify that the TcpForwarder utility and HTTP/2 frame parsing functions
work correctly with real HTTP/2 traffic. We use grpcbin as a neutral HTTP/2 test
server to validate the utility functionality.
"""

import threading
import pytest

from hyperframe.frame import SettingsFrame

from localstack_extensions.utils.h2_proxy import (
    get_headers_from_frames,
    TcpForwarder,
)

# Import from conftest - pytest automatically loads conftest.py
from .conftest import HTTP2_PREFACE, SETTINGS_FRAME, parse_server_frames


class TestTcpForwarderConnection:
    """Tests for TcpForwarder connection management."""

    def test_connect_to_grpcbin(self, grpcbin_host, grpcbin_insecure_port):
        """Test that TcpForwarder can connect to grpcbin."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        try:
            # Connection is made in __init__, so if we get here, it worked
            assert forwarder.port == grpcbin_insecure_port
            assert forwarder.host == grpcbin_host
        finally:
            forwarder.close()

    def test_connect_and_close(self, grpcbin_host, grpcbin_insecure_port):
        """Test connect and close cycle."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        assert forwarder.port == grpcbin_insecure_port
        forwarder.close()
        # Verify close succeeded without raising an exception

    def test_multiple_connect_close_cycles(self, grpcbin_host, grpcbin_insecure_port):
        """Test multiple connect/close cycles."""
        for _ in range(3):
            forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
            forwarder.close()


class TestTcpForwarderSendReceive:
    """Tests for TcpForwarder send/receive operations."""

    def test_send_and_receive(self, grpcbin_host, grpcbin_insecure_port):
        """Test sending data and receiving response."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        received_data = []
        receive_complete = threading.Event()

        def callback(data):
            received_data.append(data)
            receive_complete.set()

        try:
            # Start receive loop in background thread
            receive_thread = threading.Thread(
                target=forwarder.receive_loop, args=(callback,), daemon=True
            )
            receive_thread.start()

            # Send HTTP/2 preface
            forwarder.send(HTTP2_PREFACE)

            # Wait for response (with timeout)
            if not receive_complete.wait(timeout=5.0):
                pytest.fail("Did not receive response within timeout")

            # Should have received at least one chunk
            assert len(received_data) > 0
            # Response should contain data (at least a SETTINGS frame)
            total_bytes = sum(len(d) for d in received_data)
            assert total_bytes >= 9, (
                "Should receive at least one frame header (9 bytes)"
            )

        finally:
            forwarder.close()

    def test_bidirectional_http2_exchange(self, grpcbin_host, grpcbin_insecure_port):
        """Test bidirectional HTTP/2 settings exchange."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        received_data = []
        first_response = threading.Event()

        def callback(data):
            received_data.append(data)
            first_response.set()

        try:
            # Start receive loop
            receive_thread = threading.Thread(
                target=forwarder.receive_loop, args=(callback,), daemon=True
            )
            receive_thread.start()

            # Send HTTP/2 preface
            forwarder.send(HTTP2_PREFACE)

            # Wait for initial response
            first_response.wait(timeout=5.0)
            assert len(received_data) > 0

            # Send SETTINGS frame
            forwarder.send(SETTINGS_FRAME)

        finally:
            forwarder.close()


class TestTcpForwarderErrorHandling:
    """Tests for error handling in TcpForwarder."""

    def test_connection_to_invalid_port(self, grpcbin_host):
        """Test connecting to a port that's not listening."""
        with pytest.raises((ConnectionRefusedError, OSError)):
            TcpForwarder(port=59999, host=grpcbin_host)

    def test_close_after_failed_connection(self, grpcbin_host, grpcbin_insecure_port):
        """Test that close works even after error conditions."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        forwarder.close()
        # Close again should not raise
        forwarder.close()

    def test_send_after_close(self, grpcbin_host, grpcbin_insecure_port):
        """Test sending after close raises appropriate error."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        forwarder.close()

        with pytest.raises(OSError):
            forwarder.send(b"data")


class TestTcpForwarderConcurrency:
    """Tests for concurrent operations in TcpForwarder."""

    def test_multiple_sends(self, grpcbin_host, grpcbin_insecure_port):
        """Test multiple sequential sends (no exception = success)."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        try:
            forwarder.send(HTTP2_PREFACE)
            forwarder.send(SETTINGS_FRAME)
            forwarder.send(b"\x00\x00\x00\x04\x01\x00\x00\x00\x00")  # SETTINGS ACK
        finally:
            forwarder.close()

    def test_concurrent_connections(self, grpcbin_host, grpcbin_insecure_port):
        """Test multiple concurrent TcpForwarder connections."""
        forwarders = []
        try:
            for _ in range(3):
                forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
                forwarders.append(forwarder)

            # All connections should be established
            assert len(forwarders) == 3

            # Send preface to all
            for forwarder in forwarders:
                forwarder.send(HTTP2_PREFACE)

        finally:
            for forwarder in forwarders:
                forwarder.close()


class TestHttp2FrameParsing:
    """Tests for HTTP/2 frame parsing with live server traffic."""

    def test_capture_settings_frame(self, grpcbin_host, grpcbin_insecure_port):
        """Test capturing a SETTINGS frame from grpcbin."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        received_data = []
        done = threading.Event()
        thread_started = threading.Event()

        def callback(data):
            received_data.append(data)
            done.set()

        def receive_with_signal():
            thread_started.set()
            forwarder.receive_loop(callback)

        try:
            receive_thread = threading.Thread(target=receive_with_signal, daemon=True)
            receive_thread.start()
            thread_started.wait(timeout=1.0)  # Wait for receive thread to be ready

            forwarder.send(HTTP2_PREFACE + SETTINGS_FRAME)
            done.wait(timeout=5.0)

            # Parse the server response (no preface expected in server data)
            server_data = b"".join(received_data)
            frames = parse_server_frames(server_data)

            # Check that we got frames
            assert len(frames) > 0

            # First frame should be SETTINGS
            settings_frames = [f for f in frames if isinstance(f, SettingsFrame)]
            assert len(settings_frames) > 0, (
                "Should receive at least one SETTINGS frame"
            )
        finally:
            forwarder.close()

    def test_parse_server_settings(self, grpcbin_host, grpcbin_insecure_port):
        """Test parsing the server's SETTINGS values."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        received_data = []
        done = threading.Event()
        thread_started = threading.Event()

        def callback(data):
            received_data.append(data)
            done.set()

        def receive_with_signal():
            thread_started.set()
            forwarder.receive_loop(callback)

        try:
            receive_thread = threading.Thread(target=receive_with_signal, daemon=True)
            receive_thread.start()
            thread_started.wait(timeout=1.0)  # Wait for receive thread to be ready

            forwarder.send(HTTP2_PREFACE + SETTINGS_FRAME)
            done.wait(timeout=5.0)

            server_data = b"".join(received_data)
            frames = parse_server_frames(server_data)

            settings_frames = [f for f in frames if isinstance(f, SettingsFrame)]
            assert len(settings_frames) > 0

            # SETTINGS frame should have settings attribute
            settings_frame = settings_frames[0]
            assert hasattr(settings_frame, "settings")
        finally:
            forwarder.close()

    def test_http2_handshake_completes(self, grpcbin_host, grpcbin_insecure_port):
        """Test that we can complete an HTTP/2 handshake with settings exchange."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        received_data = []
        first_response = threading.Event()

        def callback(data):
            received_data.append(data)
            first_response.set()

        try:
            receive_thread = threading.Thread(
                target=forwarder.receive_loop, args=(callback,), daemon=True
            )
            receive_thread.start()

            # Send HTTP/2 preface and SETTINGS
            forwarder.send(HTTP2_PREFACE + SETTINGS_FRAME)

            # Wait for server's initial frames
            first_response.wait(timeout=5.0)
            assert len(received_data) > 0, "Should receive server SETTINGS"

            # Send SETTINGS ACK to complete handshake
            forwarder.send(b"\x00\x00\x00\x04\x01\x00\x00\x00\x00")  # SETTINGS ACK
        finally:
            forwarder.close()

    def test_full_connection_sequence(self, grpcbin_host, grpcbin_insecure_port):
        """Test a full HTTP/2 connection sequence with grpcbin."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        received_data = []
        first_response = threading.Event()

        def callback(data):
            received_data.append(data)
            first_response.set()

        try:
            receive_thread = threading.Thread(
                target=forwarder.receive_loop, args=(callback,), daemon=True
            )
            receive_thread.start()

            # Send preface and SETTINGS frame together
            forwarder.send(HTTP2_PREFACE + SETTINGS_FRAME)
            first_response.wait(timeout=5.0)

            # Parse server response frames
            server_data = b"".join(received_data)
            frames = parse_server_frames(server_data)

            assert len(frames) >= 1, "Should receive at least one frame from server"

            # Verify frame types
            frame_types = [type(f).__name__ for f in frames]
            assert "SettingsFrame" in frame_types, (
                f"Expected SettingsFrame, got: {frame_types}"
            )

        finally:
            forwarder.close()

    def test_headers_extraction_from_raw_traffic(
        self, grpcbin_host, grpcbin_insecure_port
    ):
        """Test that get_headers_from_frames works with live traffic."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        received_data = []
        done = threading.Event()

        def callback(data):
            received_data.append(data)
            done.set()

        try:
            receive_thread = threading.Thread(
                target=forwarder.receive_loop, args=(callback,), daemon=True
            )
            receive_thread.start()

            forwarder.send(HTTP2_PREFACE + SETTINGS_FRAME)
            done.wait(timeout=5.0)

            server_data = b"".join(received_data)
            frames = parse_server_frames(server_data)
            headers = get_headers_from_frames(frames)

            # Server response has SETTINGS, not HEADERS, so headers should be empty
            assert len(headers) == 0, "SETTINGS frames should not produce headers"
        finally:
            forwarder.close()
