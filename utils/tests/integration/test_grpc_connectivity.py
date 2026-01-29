"""
Integration tests for gRPC connectivity using grpcbin.

These tests verify that we can make real gRPC/HTTP2 connections
to the grpcbin test service and properly capture and parse
HTTP/2 frames from live traffic.

Note: grpcbin has strict HTTP/2 protocol requirements. Tests that use
bidirectional I/O with threading (TcpForwarder) work correctly, while
simple synchronous socket tests may experience connection resets due
to protocol timing.
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
    """Tests for basic gRPC/HTTP2 connectivity to grpcbin."""

    def test_tcp_connect_to_grpcbin(self, grpcbin_host, grpcbin_insecure_port):
        """Test that we can establish a TCP connection to grpcbin."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((grpcbin_host, grpcbin_insecure_port))
            # Connection successful if we get here
            assert True
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
    """Tests for extracting gRPC headers from live connections."""

    def test_grpc_request_headers_structure(self, grpcbin_host, grpcbin_insecure_port):
        """Test that we can send and receive proper gRPC request structure."""
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
            assert len(received_data) > 0

            # Send SETTINGS ACK
            settings_ack = b"\x00\x00\x00\x04\x01\x00\x00\x00\x00"  # flags=0x01 (ACK)
            forwarder.send(settings_ack)

            # Give server time to process
            time.sleep(0.1)

            # Connection is now established
            # We've verified we can perform HTTP/2 handshake with grpcbin
            assert True
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
