"""
Unit tests for TCP connection matcher helpers.
"""

from localstack_extensions.utils.tcp_protocol_detector import (
    create_prefix_matcher,
    create_signature_matcher,
    create_custom_matcher,
    combine_matchers,
)
from localstack_extensions.utils.docker import ProxiedDockerContainerExtension
from werkzeug.datastructures import Headers


class TestMatcherFactories:
    """Tests for matcher factory functions."""

    def test_create_prefix_matcher(self):
        """Test creating a prefix-based matcher."""
        matcher = create_prefix_matcher(b"MYPROTO")

        assert matcher(b"MYPROTO_DATA")
        assert matcher(b"MYPROTO")
        assert not matcher(b"NOTMYPROTO")
        assert not matcher(b"MY")

    def test_create_signature_matcher(self):
        """Test creating a signature matcher with offset."""
        # Match signature at offset 4
        matcher = create_signature_matcher(b"\xaa\xbb", offset=4)

        assert matcher(b"\x00\x00\x00\x00\xaa\xbb\xcc")
        assert matcher(b"\x00\x00\x00\x00\xaa\xbb")
        assert not matcher(b"\xaa\xbb\xcc")  # Wrong offset
        assert not matcher(b"\x00\x00\x00\x00\xcc\xdd")  # Wrong signature
        assert not matcher(b"\x00\x00\x00\x00\xaa")  # Incomplete

    def test_create_custom_matcher(self):
        """Test creating a custom matcher."""

        def my_check(data):
            return len(data) > 5 and data[5] == 0xFF

        matcher = create_custom_matcher(my_check)

        assert matcher(b"\x00\x00\x00\x00\x00\xff")
        assert matcher(b"\x00\x00\x00\x00\x00\xff\xff")
        assert not matcher(b"\x00\x00\x00\x00\x00\x00")
        assert not matcher(b"\x00\x00\x00\x00\x00")  # Too short

    def test_combine_matchers(self):
        """Test combining multiple matchers."""
        matcher1 = create_prefix_matcher(b"PROTO1")
        matcher2 = create_prefix_matcher(b"PROTO2")
        combined = combine_matchers(matcher1, matcher2)

        # Should match first protocol
        assert combined(b"PROTO1_DATA")

        # Should match second protocol
        assert combined(b"PROTO2_DATA")

        # Should not match other data
        assert not combined(b"PROTO3_DATA")
        assert not combined(b"NOTAPROTOCOL")


class TestMatcherEdgeCases:
    """Tests for edge cases in matchers."""

    def test_empty_data(self):
        """Test matchers with empty data."""
        prefix_matcher = create_prefix_matcher(b"TEST")
        sig_matcher = create_signature_matcher(b"SIG", offset=4)

        assert not prefix_matcher(b"")
        assert not sig_matcher(b"")

    def test_insufficient_data(self):
        """Test matchers with insufficient data."""
        sig_matcher = create_signature_matcher(b"SIGNATURE", offset=4)

        # Not enough bytes to reach offset + signature length
        assert not sig_matcher(b"\x00\x00\x00\x00SIG")
        assert not sig_matcher(b"\x00\x00\x00")

    def test_matcher_with_extra_data(self):
        """Test that matchers work with extra trailing data."""
        matcher = create_prefix_matcher(b"PREFIX")

        # Should match even with lots of extra data
        assert matcher(b"PREFIX" + b"\xff" * 1000)


class TestRealWorldUsage:
    """Tests for real-world usage patterns."""

    def test_extension_with_custom_protocol_matcher(self):
        """Test using custom matchers in an extension context."""

        class CustomProtocolExtension(ProxiedDockerContainerExtension):
            name = "custom"

            def __init__(self):
                super().__init__(
                    image_name="custom:latest",
                    container_ports=[9999],
                    tcp_ports=[9999],
                )

            def tcp_connection_matcher(self, data: bytes) -> bool:
                # Match custom protocol with magic bytes at offset 4
                matcher = create_signature_matcher(b"\xde\xad\xbe\xef", offset=4)
                return matcher(data)

            def should_proxy_request(self, headers: Headers) -> bool:
                return False

        extension = CustomProtocolExtension()
        assert hasattr(extension, "tcp_connection_matcher")

        # Test the matcher
        valid_data = b"\x00\x00\x00\x00\xde\xad\xbe\xef\xff"
        assert extension.tcp_connection_matcher(valid_data)

        invalid_data = b"\x00\x00\x00\x00\xff\xff\xff\xff"
        assert not extension.tcp_connection_matcher(invalid_data)

    def test_extension_with_combined_matchers(self):
        """Test using combined matchers in an extension."""

        class MultiProtocolExtension(ProxiedDockerContainerExtension):
            name = "multi-protocol"

            def __init__(self):
                super().__init__(
                    image_name="multi:latest",
                    container_ports=[5432],
                    tcp_ports=[5432],
                )

            def tcp_connection_matcher(self, data: bytes) -> bool:
                # Match either of two protocol variants
                variant1 = create_prefix_matcher(b"V1:")
                variant2 = create_prefix_matcher(b"V2:")
                return combine_matchers(variant1, variant2)(data)

            def should_proxy_request(self, headers: Headers) -> bool:
                return False

        extension = MultiProtocolExtension()

        # Should match both variants
        assert extension.tcp_connection_matcher(b"V1:DATA")
        assert extension.tcp_connection_matcher(b"V2:DATA")
        assert not extension.tcp_connection_matcher(b"V3:DATA")

    def test_extension_with_inline_matcher(self):
        """Test using an inline matcher function."""

        class InlineMatcherExtension(ProxiedDockerContainerExtension):
            name = "inline"

            def __init__(self):
                super().__init__(
                    image_name="inline:latest",
                    container_ports=[8888],
                    tcp_ports=[8888],
                )

            def tcp_connection_matcher(self, data: bytes) -> bool:
                # Inline custom logic without helper functions
                return len(data) >= 8 and data.startswith(b"MAGIC") and data[7] == 0x42

            def should_proxy_request(self, headers: Headers) -> bool:
                return False

        extension = InlineMatcherExtension()
        assert extension.tcp_connection_matcher(b"MAGIC\x00\x00\x42")
        assert not extension.tcp_connection_matcher(b"MAGIC\x00\x00\x43")
