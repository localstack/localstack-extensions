"""
Shared pytest configuration for the utils package tests.

Test categories:
- unit: No Docker or LocalStack required (pure functions with mocks)
- integration: Docker required (uses grpcbin), no LocalStack
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (no Docker/LocalStack required)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (Docker required, no LocalStack)"
    )


def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their location in the test directory.
    Tests in tests/unit/ are marked as 'unit'.
    Tests in tests/integration/ are marked as 'integration'.
    """
    for item in items:
        # Get the path relative to the tests directory
        test_path = str(item.fspath)

        if "/tests/unit/" in test_path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in test_path:
            item.add_marker(pytest.mark.integration)
