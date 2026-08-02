"""Pytest configuration — register custom markers."""
import pytest

pytest_plugins = []


def pytest_configure(config):
    config.addinivalue_line("markers", "timeout: mark test with timeout (seconds)")
