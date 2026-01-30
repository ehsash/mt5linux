"""Feature tests for MT5 connection lifecycle (Epic 2).

Tests:
    - Connection establishment
    - Connection status and health
    - Terminal info retrieval
    - Version info
    - Reconnection after temporary disconnect
"""

from typing import Any

import pytest

pytestmark = [pytest.mark.feature_short]


class TestConnectionEstablishment:
    """Test connection establishment and basic connectivity."""

    def test_connection_is_established(self, mt5: Any) -> None:
        """Verify MT5 connection is established."""
        assert mt5.is_connected is True

    def test_terminal_info_available(self, mt5: Any) -> None:
        """Verify terminal info can be retrieved."""
        info = mt5.terminal_info()
        assert info is not None
        assert hasattr(info, "name")
        assert hasattr(info, "path")
        assert hasattr(info, "connected")

    def test_terminal_is_connected_to_broker(self, mt5: Any) -> None:
        """Verify terminal is connected to broker server."""
        info = mt5.terminal_info()
        assert info is not None
        # connected attribute indicates broker connection
        assert info.connected is True, "Terminal not connected to broker"

    def test_version_info_available(self, mt5: Any) -> None:
        """Verify MT5 version info is available."""
        version = mt5.version()
        assert version is not None
        assert len(version) >= 3  # (build, release_date, build_name)

    def test_last_error_no_error_initially(self, mt5: Any) -> None:
        """Verify no error after successful connection."""
        error = mt5.last_error()
        assert error is not None
        # Error code 1 means success (RES_S_OK)
        assert error[0] == 1, f"Unexpected error: {error}"


class TestConnectionStatus:
    """Test connection status reporting."""

    def test_connection_status_dict(self, mt5: Any) -> None:
        """Verify connection_status returns detailed status."""
        status = mt5.connection_status()
        assert isinstance(status, dict)
        # With auto_connect=True, should have lifecycle_status
        assert "lifecycle_status" in status or len(status) > 0

    def test_is_connected_property(self, mt5: Any) -> None:
        """Verify is_connected property works correctly."""
        assert isinstance(mt5.is_connected, bool)
        assert mt5.is_connected is True


class TestConnectionResilience:
    """Test connection resilience and recovery."""

    def test_multiple_terminal_info_calls(self, mt5: Any) -> None:
        """Verify connection handles multiple rapid calls."""
        for _ in range(10):
            info = mt5.terminal_info()
            assert info is not None

    def test_multiple_account_info_calls(self, mt5: Any) -> None:
        """Verify connection handles multiple account info calls."""
        for _ in range(5):
            info = mt5.account_info()
            assert info is not None

    def test_connection_survives_symbol_operations(self, mt5: Any) -> None:
        """Verify connection survives various symbol operations."""
        # Get total symbols
        total = mt5.symbols_total()
        assert total is not None
        assert total > 0

        # Get some symbols
        symbols = mt5.symbols_get()
        assert symbols is not None
        assert len(symbols) > 0

        # Connection should still be alive
        assert mt5.is_connected is True


@pytest.mark.feature_long
class TestConnectionRecovery:
    """Test connection recovery scenarios.

    These tests are longer as they may involve timeouts.
    """

    def test_connection_after_idle_period(self, mt5: Any) -> None:
        """Verify connection survives brief idle period."""
        import time

        # Wait for a brief period
        time.sleep(5)

        # Connection should still work
        assert mt5.is_connected is True
        info = mt5.terminal_info()
        assert info is not None
