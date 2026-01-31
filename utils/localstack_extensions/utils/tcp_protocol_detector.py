"""
Helper functions for creating TCP connection matchers.

This module provides utilities for extensions to create custom matchers
that identify their TCP connections from initial bytes.
"""

import logging
from typing import Callable

LOG = logging.getLogger(__name__)

# Type alias for matcher functions
ConnectionMatcher = Callable[[bytes], bool]


def create_prefix_matcher(prefix: bytes) -> ConnectionMatcher:
    """
    Create a matcher that matches a specific byte prefix.

    Args:
        prefix: The byte prefix to match

    Returns:
        A matcher function

    Example:
        # Match Redis RESP protocol
        matcher = create_prefix_matcher(b"*")
    """

    def matcher(data: bytes) -> bool:
        return data.startswith(prefix)

    return matcher


def create_signature_matcher(signature: bytes, offset: int = 0) -> ConnectionMatcher:
    """
    Create a matcher that matches bytes at a specific offset.

    Args:
        signature: The byte sequence to match
        offset: The offset where the signature should appear

    Returns:
        A matcher function

    Example:
        # Match PostgreSQL protocol version at offset 4
        matcher = create_signature_matcher(b"\\x00\\x03\\x00\\x00", offset=4)
    """

    def matcher(data: bytes) -> bool:
        if len(data) < offset + len(signature):
            return False
        return data[offset : offset + len(signature)] == signature

    return matcher


def create_custom_matcher(check_func: Callable[[bytes], bool]) -> ConnectionMatcher:
    """
    Create a matcher from a custom checking function.

    Args:
        check_func: Function that takes bytes and returns bool

    Returns:
        A matcher function

    Example:
        def is_my_protocol(data):
            return len(data) > 10 and data[5] == 0xFF

        matcher = create_custom_matcher(is_my_protocol)
    """
    return check_func


def combine_matchers(*matchers: ConnectionMatcher) -> ConnectionMatcher:
    """
    Combine multiple matchers with OR logic.

    Returns True if any matcher returns True.

    Args:
        *matchers: Variable number of matcher functions

    Returns:
        A combined matcher function

    Example:
        # Match either of two custom protocols
        matcher1 = create_prefix_matcher(b"PROTO1")
        matcher2 = create_prefix_matcher(b"PROTO2")
        combined = combine_matchers(matcher1, matcher2)
    """

    def combined(data: bytes) -> bool:
        return any(matcher(data) for matcher in matchers)

    return combined


# Export all functions
__all__ = [
    "ConnectionMatcher",
    "create_prefix_matcher",
    "create_signature_matcher",
    "create_custom_matcher",
    "combine_matchers",
]
