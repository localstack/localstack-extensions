"""
Integration tests for TcpForwarder against a live grpcbin service.

These tests verify that TcpForwarder can establish real TCP connections
and properly handle bidirectional HTTP/2 traffic.
"""

import threading
import time
import pytest

from localstack_extensions.utils.h2_proxy import TcpForwarder


# HTTP/2 connection preface
HTTP2_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"


class TestTcpForwarderConnection:
    """Tests for TcpForwarder connection to grpcbin."""

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
        forwarder.close()
        # Should not raise

    def test_multiple_connect_close_cycles(self, grpcbin_host, grpcbin_insecure_port):
        """Test multiple connect/close cycles."""
        for _ in range(3):
            forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
            forwarder.close()


class TestTcpForwarderSendReceive:
    """Tests for TcpForwarder send/receive operations with grpcbin."""

    def test_send_http2_preface(self, grpcbin_host, grpcbin_insecure_port):
        """Test sending HTTP/2 preface through TcpForwarder."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        try:
            forwarder.send(HTTP2_PREFACE)
            # If we get here without exception, send worked
            assert True
        finally:
            forwarder.close()

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
            assert total_bytes >= 9, "Should receive at least one frame header (9 bytes)"

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

            # Send SETTINGS frame
            settings_frame = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"
            forwarder.send(settings_frame)

            # Give server time to respond
            time.sleep(0.5)

            # Verify we got data
            assert len(received_data) > 0

        finally:
            forwarder.close()


class TestTcpForwarderHttp2Handling:
    """Tests for HTTP/2 specific handling in TcpForwarder."""

    def test_http2_preface_response_parsing(self, grpcbin_host, grpcbin_insecure_port):
        """Test that responses to HTTP/2 preface can be parsed."""
        from localstack_extensions.utils.h2_proxy import get_frames_from_http2_stream

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

            forwarder.send(HTTP2_PREFACE)
            done.wait(timeout=5.0)

            # Parse received data as HTTP/2 frames
            all_data = HTTP2_PREFACE + b"".join(received_data)
            frames = list(get_frames_from_http2_stream(all_data))

            assert len(frames) > 0, "Should parse frames from response"

        finally:
            forwarder.close()

    def test_server_settings_frame(self, grpcbin_host, grpcbin_insecure_port):
        """Test that server sends SETTINGS frame after preface."""
        from localstack_extensions.utils.h2_proxy import get_frames_from_http2_stream
        from hyperframe.frame import SettingsFrame

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

            forwarder.send(HTTP2_PREFACE)
            done.wait(timeout=5.0)

            # Parse and verify SETTINGS frame
            all_data = HTTP2_PREFACE + b"".join(received_data)
            frames = list(get_frames_from_http2_stream(all_data))

            settings_frames = [f for f in frames if isinstance(f, SettingsFrame)]
            assert len(settings_frames) > 0, "Server should send SETTINGS frame"

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
        """Test multiple sequential sends."""
        forwarder = TcpForwarder(port=grpcbin_insecure_port, host=grpcbin_host)
        try:
            # Send preface first
            forwarder.send(HTTP2_PREFACE)
            # Then settings
            settings_frame = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"
            forwarder.send(settings_frame)
            # Then settings ACK
            settings_ack = b"\x00\x00\x00\x04\x01\x00\x00\x00\x00"
            forwarder.send(settings_ack)
            # All sends should succeed
            assert True
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
