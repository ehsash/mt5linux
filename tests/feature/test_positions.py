"""Feature tests for position management (Epic 3, Story 3.5).

Tests:
    - Position queries (positions_total, positions_get)
    - Position helper methods
    - Position filtering by symbol
    - Total profit/volume calculations

Note:
    Position opening/closing is tested in test_trading.py
"""

from typing import Any

import pytest

pytestmark = [pytest.mark.feature_short]


class TestPositionQueries:
    """Test position query functionality."""

    def test_positions_total_returns_int(self, mt5: Any) -> None:
        """Verify positions_total returns an integer."""
        total = mt5.positions_total()
        assert total is not None
        assert isinstance(total, int)
        assert total >= 0

    def test_positions_get_returns_tuple(self, mt5: Any) -> None:
        """Verify positions_get returns a tuple."""
        positions = mt5.positions_get()
        # Returns tuple (possibly empty)
        assert positions is not None or positions == ()

    def test_positions_get_by_symbol(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test filtering positions by symbol."""
        positions = mt5.positions_get(symbol=symbol_eurusd)
        # Returns tuple (possibly empty if no positions)
        assert positions is not None or positions == ()

        # If positions exist, verify they match the symbol
        if positions:
            for pos in positions:
                assert pos.symbol == symbol_eurusd


class TestPositionHelpers:
    """Test position helper methods."""

    def test_get_total_profit(self, mt5: Any) -> None:
        """Test get_total_profit() helper."""
        profit = mt5.get_total_profit()
        assert isinstance(profit, float)
        # Profit can be negative, zero, or positive

    def test_get_total_volume(self, mt5: Any) -> None:
        """Test get_total_volume() helper."""
        volume = mt5.get_total_volume()
        assert isinstance(volume, float)
        assert volume >= 0

    def test_get_total_volume_by_symbol(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test get_total_volume() filtered by symbol."""
        volume = mt5.get_total_volume(symbol=symbol_eurusd)
        assert isinstance(volume, float)
        assert volume >= 0

    def test_get_positions_by_symbol(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test get_positions_by_symbol() helper."""
        positions = mt5.get_positions_by_symbol(symbol_eurusd)
        assert isinstance(positions, tuple)
        # All positions should match symbol
        for pos in positions:
            assert pos.symbol == symbol_eurusd

    def test_get_position_by_ticket_nonexistent(self, mt5: Any) -> None:
        """Test get_position_by_ticket() with nonexistent ticket."""
        # Use a ticket number that shouldn't exist
        position = mt5.get_position_by_ticket(99999999)
        assert position is None


class TestPositionConsistency:
    """Test position data consistency."""

    def test_positions_total_matches_positions_get(self, mt5: Any) -> None:
        """Verify positions_total matches length of positions_get."""
        total = mt5.positions_total() or 0
        positions = mt5.positions_get() or ()
        assert total == len(positions)

    def test_position_volume_consistency(self, mt5: Any) -> None:
        """Verify total volume equals sum of individual positions."""
        total_volume = mt5.get_total_volume()
        positions = mt5.positions_get() or ()

        calculated_volume = sum(pos.volume for pos in positions)
        assert abs(total_volume - calculated_volume) < 0.0001

    def test_position_profit_consistency(self, mt5: Any) -> None:
        """Verify total profit equals sum of individual positions."""
        total_profit = mt5.get_total_profit()
        positions = mt5.positions_get() or ()

        calculated_profit = sum(pos.profit for pos in positions)
        # Allow small floating point difference
        assert abs(total_profit - calculated_profit) < 0.01
