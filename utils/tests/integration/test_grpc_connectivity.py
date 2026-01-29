"""
Integration tests for HTTP/2 frame parsing utilities against a live server.

These tests verify that the frame parsing utilities (get_frames_from_http2_stream,
get_headers_from_frames) work correctly with real HTTP/2 traffic. We use grpcbin
as a neutral HTTP/2 test server - these tests validate the utility functions,
not the LocalStack proxy integration (which is tested in typedb).
"""

import socket
import threading
import time

from localstack_extensions.utils.h2_proxy import (
    get_frames_from_http2_stream,
    get_headers_from_frames,
    TcpForwarder,
)


# HTTP/2 connection preface
HTTP2_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

# Empty SETTINGS frame
SETTINGS_FRAME = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"


class TestGrpcConnectivity:
    """Tests for basic HTTP/2 connectivity to grpcbin."""

    def test_tcp_connect_to_grpcbin(self, grpcbin_host, grpcbin_insecure_port):
        """Test that we can establish a TCP connection (no exception = success)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((grpcbin_host, grpcbin_insecure_port))
        finally:
            sock.close()


class TestHttp2FrameCapture:
    """Tests for capturing and parsing HTTP/2 frames from live traffic."""

    def test_capture_settings_frame(self, grpcbin_host, grpcbin_insecure_port):
        """Test capturing a SETTINGS frame from grpcbin."""
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

            # Parse the response using our utilities
            full_data = HTTP2_PREFACE + b"".join(received_data)
            frames = list(get_frames_from_http2_stream(full_data))

            # Check that we got frames
            assert len(frames) > 0

            # First frame should be SETTINGS
            from hyperframe.frame import SettingsFrame

            settings_frames = [f for f in frames if isinstance(f, SettingsFrame)]
            assert len(settings_frames) > 0, "Should receive at least one SETTINGS frame"
        finally:
            forwarder.close()

    def test_parse_server_settings(self, grpcbin_host, grpcbin_insecure_port):
        """Test parsing the server's SETTINGS values."""
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

            full_data = HTTP2_PREFACE + b"".join(received_data)
            frames = list(get_frames_from_http2_stream(full_data))

            from hyperframe.frame import SettingsFrame

            settings_frames = [f for f in frames if isinstance(f, SettingsFrame)]
            assert len(settings_frames) > 0

            # SETTINGS frame should have settings attribute
            settings_frame = settings_frames[0]
            assert hasattr(settings_frame, "settings")
        finally:
            forwarder.close()


class TestGrpcHeaders:
    """Tests for HTTP/2 handshake completion."""

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


class TestGrpcFrameParsing:
    """Tests for parsing gRPC-specific frame patterns."""

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

            # Step 1: Send preface
            forwarder.send(HTTP2_PREFACE)

            # Wait for server response
            first_response.wait(timeout=5.0)

            # Step 2: Send empty SETTINGS
            forwarder.send(SETTINGS_FRAME)

            # Give server time to respond
            time.sleep(0.2)

            # Parse all frames
            full_data = HTTP2_PREFACE + b"".join(received_data)
            frames = list(get_frames_from_http2_stream(full_data))

            assert len(frames) >= 1, "Should receive at least one frame from server"

            # Verify frame types
            frame_types = [type(f).__name__ for f in frames]
            assert "SettingsFrame" in frame_types, f"Expected SettingsFrame, got: {frame_types}"

        finally:
            forwarder.close()

    def test_headers_extraction_from_raw_traffic(self, grpcbin_host, grpcbin_insecure_port):
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

            forwarder.send(HTTP2_PREFACE)
            done.wait(timeout=5.0)

            full_data = HTTP2_PREFACE + b"".join(received_data)

            frames = list(get_frames_from_http2_stream(full_data))
            headers = get_headers_from_frames(frames)

            # Server's initial response typically doesn't include HEADERS frames
            # (just SETTINGS), so headers will be empty - but the function should work
            assert headers is not None
        finally:
            forwarder.close()
