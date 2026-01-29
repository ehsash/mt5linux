"""Integration test that requires a running rpyc server.

This test is skipped during unit testing (pytest -m unit).
To run: ensure rpyc server is running on port 1235, then run without -m unit.
"""
import pytest


@pytest.mark.feature_long
def test_basic_integration() -> None:
    """Basic integration test with real rpyc server."""
    from mt5linux import MetaTrader5

    # Use auto_connect=False for legacy behavior (assumes rpyc server already running)
    mt5 = MetaTrader5(port=1235, auto_connect=False)
    mt5.initialize()
    # Verify terminal_info returns valid data (integration check)
    terminal_info = mt5.terminal_info()
    assert terminal_info is not None, "terminal_info() should return data"
    mt5.shutdown()