"""
Unit tests for HTTP/2 frame parsing utilities.

These tests verify the parsing of HTTP/2 frames from raw byte streams,
including the HTTP/2 preface, settings frames, and headers frames.
No Docker or network access required.
"""

from hyperframe.frame import SettingsFrame, HeadersFrame, WindowUpdateFrame

from localstack_extensions.utils.h2_proxy import (
    get_frames_from_http2_stream,
    get_headers_from_frames,
    get_headers_from_data_stream,
)


# HTTP/2 connection preface (24 bytes)
HTTP2_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"


class TestParseHttp2PrefaceAndFrames:
    """Tests for parsing HTTP/2 frames from captured data."""

    # This data is a dump taken from a browser request - includes preface, settings, and headers
    SAMPLE_HTTP2_DATA = (
        b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n\x00\x00\x18\x04\x00\x00\x00\x00\x00\x00\x01\x00\x01"
        b"\x00\x00\x00\x02\x00\x00\x00\x00\x00\x04\x00\x02\x00\x00\x00\x05\x00\x00@\x00\x00\x00"
        b"\x04\x08\x00\x00\x00\x00\x00\x00\xbf\x00\x01\x00\x01V\x01%\x00\x00\x00\x03\x00\x00\x00"
        b"\x00\x15C\x87\xd5\xaf~MZw\x7f\x05\x8eb*\x0eA\xd0\x84\x8c\x9dX\x9c\xa3\xa13\xffA\x96"
        b"\xa0\xe4\x1d\x13\x9d\t^\x83\x90t!#'U\xc9A\xed\x92\xe3M\xb8\xe7\x87z\xbe\xd0\x7ff\xa2"
        b"\x81\xb0\xda\xe0S\xfa\xd02\x1a\xa4\x9d\x13\xfd\xa9\x92\xa4\x96\x854\x0c\x8aj\xdc\xa7"
        b"\xe2\x81\x02\xe1o\xedK;\xdc\x0bM.\x0f\xedLE'S\xb0 \x04\x00\x08\x02\xa6\x13XYO\xe5\x80"
        b"\xb4\xd2\xe0S\x83\xf9c\xe7Q\x8b-Kp\xdd\xf4Z\xbe\xfb@\x05\xdbP\x92\x9b\xd9\xab\xfaRB"
        b"\xcb@\xd2_\xa5#\xb3\xe9OhL\x9f@\x94\x19\x08T!b\x1e\xa4\xd8z\x16\xb0\xbd\xad*\x12\xb5"
        b"%L\xe7\x93\x83\xc5\x83\x7f@\x95\x19\x08T!b\x1e\xa4\xd8z\x16\xb0\xbd\xad*\x12\xb4\xe5"
        b"\x1c\x85\xb1\x1f\x89\x1d\xa9\x9c\xf6\x1b\xd8\xd2c\xd5s\x95\x9d)\xad\x17\x18`u\xd6\xbd"
        b"\x07 \xe8BFN\xab\x92\x83\xdb#\x1f@\x85=\x86\x98\xd5\x7f\x94\x9d)\xad\x17\x18`u\xd6\xbd"
        b"\x07 \xe8BFN\xab\x92\x83\xdb'@\x8aAH\xb4\xa5I'ZB\xa1?\x84-5\xa7\xd7@\x8aAH\xb4\xa5I'"
        b"Z\x93\xc8_\x83!\xecG@\x8aAH\xb4\xa5I'Y\x06I\x7f\x86@\xe9*\xc82K@\x86\xae\xc3\x1e\xc3'"
        b"\xd7\x83\xb6\x06\xbf@\x82I\x7f\x86M\x835\x05\xb1\x1f\x00\x00\x04\x08\x00\x00\x00\x00"
        b"\x03\x00\xbe\x00\x00"
    )

    def test_parse_http2_frames_from_captured_data(self):
        """Test parsing HTTP/2 frames from a real captured browser request."""
        frames = list(get_frames_from_http2_stream(self.SAMPLE_HTTP2_DATA))

        assert len(frames) > 0, "Should parse at least one frame"

        # First frame after preface should be a SETTINGS frame
        frame_types = [type(f) for f in frames]
        assert SettingsFrame in frame_types, "Should contain SETTINGS frame"

    def test_frames_contain_headers_frame(self):
        """Test that parsed frames include a HEADERS frame."""
        frames = list(get_frames_from_http2_stream(self.SAMPLE_HTTP2_DATA))
        frame_types = [type(f) for f in frames]
        assert HeadersFrame in frame_types, "Should contain HEADERS frame"

    def test_parse_preface_only(self):
        """Test parsing just the HTTP/2 preface (no frames expected)."""
        frames = list(get_frames_from_http2_stream(HTTP2_PREFACE))
        # The preface alone doesn't produce frames (it's consumed as preface)
        assert frames == [], "HTTP/2 preface alone should not produce frames"

    def test_parse_preface_with_settings(self):
        """Test parsing preface followed by a SETTINGS frame."""
        # SETTINGS frame: type=0x04, flags=0x00, stream=0, length=0 (empty settings)
        settings_frame = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"
        data = HTTP2_PREFACE + settings_frame

        frames = list(get_frames_from_http2_stream(data))
        assert len(frames) == 1
        assert isinstance(frames[0], SettingsFrame)


class TestExtractHeaders:
    """Tests for extracting headers from HTTP/2 frames."""

    SAMPLE_HTTP2_DATA = TestParseHttp2PrefaceAndFrames.SAMPLE_HTTP2_DATA

    def test_extract_headers_from_frames(self):
        """Test extracting headers from parsed frames."""
        frames = list(get_frames_from_http2_stream(self.SAMPLE_HTTP2_DATA))
        headers = get_headers_from_frames(frames)

        assert len(headers) > 0, "Should extract at least one header"

    def test_extract_pseudo_headers(self):
        """Test that HTTP/2 pseudo-headers are correctly extracted."""
        frames = list(get_frames_from_http2_stream(self.SAMPLE_HTTP2_DATA))
        headers = get_headers_from_frames(frames)

        # HTTP/2 pseudo-headers start with ':'
        assert headers.get(":scheme") == "https"
        assert headers.get(":method") == "OPTIONS"
        assert headers.get(":path") == "/_localstack/health"

    def test_get_headers_from_data_stream(self):
        """Test the convenience function that combines frame parsing and header extraction."""
        # Use the same data but as a list of chunks
        data_chunks = [self.SAMPLE_HTTP2_DATA[:100], self.SAMPLE_HTTP2_DATA[100:]]
        headers = get_headers_from_data_stream(data_chunks)

        assert headers.get(":scheme") == "https"
        assert headers.get(":method") == "OPTIONS"

    def test_headers_case_insensitive(self):
        """Test that headers object is case-insensitive for non-pseudo headers."""
        frames = list(get_frames_from_http2_stream(self.SAMPLE_HTTP2_DATA))
        headers = get_headers_from_frames(frames)

        # werkzeug.Headers is case-insensitive
        origin = headers.get("origin")
        if origin:
            assert headers.get("Origin") == origin
            assert headers.get("ORIGIN") == origin


class TestEmptyAndInvalidData:
    """Tests for edge cases with empty or invalid data."""

    def test_empty_data(self):
        """Test parsing empty data returns empty list."""
        frames = list(get_frames_from_http2_stream(b""))
        assert frames == []

    def test_invalid_data(self):
        """Test parsing invalid/random data returns empty list (no crash)."""
        frames = list(get_frames_from_http2_stream(b"not http2 data at all"))
        assert frames == []

    def test_truncated_frame(self):
        """Test parsing truncated frame data returns empty list."""
        # Start of a valid HTTP/2 preface but truncated
        truncated = b"PRI * HTTP/2.0\r\n"
        frames = list(get_frames_from_http2_stream(truncated))
        assert frames == []

    def test_headers_from_empty_frames(self):
        """Test extracting headers from empty frame list."""
        headers = get_headers_from_frames([])
        assert len(headers) == 0

    def test_headers_from_non_header_frames(self):
        """Test extracting headers when no HEADERS frames present."""
        # SETTINGS frame only
        settings_frame = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"
        data = HTTP2_PREFACE + settings_frame

        frames = list(get_frames_from_http2_stream(data))
        headers = get_headers_from_frames(frames)

        assert len(headers) == 0, "SETTINGS frame should not produce headers"

    def test_get_headers_from_empty_data_stream(self):
        """Test get_headers_from_data_stream with empty input."""
        headers = get_headers_from_data_stream([])
        assert len(headers) == 0

    def test_get_headers_from_data_stream_with_empty_chunks(self):
        """Test get_headers_from_data_stream with list of empty chunks."""
        headers = get_headers_from_data_stream([b"", b"", b""])
        assert len(headers) == 0


class TestHttp2FrameTypes:
    """Tests for identifying different HTTP/2 frame types."""

    def test_window_update_frame(self):
        """Test parsing WINDOW_UPDATE frames."""
        # WINDOW_UPDATE frame: type=0x08, flags=0x00, stream=0, length=4
        # Window size increment: 0x00010000 (65536)
        window_update = b"\x00\x00\x04\x08\x00\x00\x00\x00\x00\x00\x01\x00\x00"
        data = HTTP2_PREFACE + window_update

        frames = list(get_frames_from_http2_stream(data))
        assert len(frames) == 1
        assert isinstance(frames[0], WindowUpdateFrame)

    def test_multiple_frame_types(self):
        """Test parsing multiple different frame types."""
        # SETTINGS frame followed by WINDOW_UPDATE frame
        settings_frame = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"
        window_update = b"\x00\x00\x04\x08\x00\x00\x00\x00\x00\x00\x01\x00\x00"
        data = HTTP2_PREFACE + settings_frame + window_update

        frames = list(get_frames_from_http2_stream(data))
        assert len(frames) == 2
        assert isinstance(frames[0], SettingsFrame)
        assert isinstance(frames[1], WindowUpdateFrame)
