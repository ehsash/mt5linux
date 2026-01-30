"""Feature tests for trading history retrieval (Epic 3, Story 3.6).

Tests:
    - Order history retrieval
    - Deal history retrieval
    - History filtering by date
    - Helper methods for history access
"""

import datetime
from typing import Any

import pytest

pytestmark = [pytest.mark.feature_short]


class TestOrderHistory:
    """Test order history retrieval."""

    def test_history_orders_total(self, mt5: Any) -> None:
        """Test getting total orders in history."""
        # Get history for last 30 days
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        total = mt5.history_orders_total(date_from, date_to)
        assert total is not None
        assert isinstance(total, int)
        assert total >= 0

    def test_history_orders_get(self, mt5: Any) -> None:
        """Test getting order history."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        orders = mt5.history_orders_get(date_from, date_to)
        # Returns tuple (possibly empty)
        assert orders is not None or orders == ()

    def test_history_orders_get_by_position(self, mt5: Any) -> None:
        """Test filtering order history by position."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        # Get all orders first
        orders = mt5.history_orders_get(date_from, date_to)
        if orders and len(orders) > 0:
            # Try to filter by first order's position
            position_id = orders[0].position_id
            filtered = mt5.history_orders_get(position=position_id)
            assert filtered is not None or filtered == ()

    def test_history_orders_get_by_ticket(self, mt5: Any) -> None:
        """Test getting specific order by ticket."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        orders = mt5.history_orders_get(date_from, date_to)
        if orders and len(orders) > 0:
            ticket = orders[0].ticket
            filtered = mt5.history_orders_get(ticket=ticket)
            assert filtered is not None or filtered == ()


class TestDealHistory:
    """Test deal history retrieval."""

    def test_history_deals_total(self, mt5: Any) -> None:
        """Test getting total deals in history."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        total = mt5.history_deals_total(date_from, date_to)
        assert total is not None
        assert isinstance(total, int)
        assert total >= 0

    def test_history_deals_get(self, mt5: Any) -> None:
        """Test getting deal history."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        deals = mt5.history_deals_get(date_from, date_to)
        # Returns tuple (possibly empty)
        assert deals is not None or deals == ()

    def test_history_deals_get_by_position(self, mt5: Any) -> None:
        """Test filtering deal history by position."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        deals = mt5.history_deals_get(date_from, date_to)
        if deals and len(deals) > 0:
            position_id = deals[0].position_id
            filtered = mt5.history_deals_get(position=position_id)
            assert filtered is not None or filtered == ()


class TestHistoryHelpers:
    """Test history helper methods."""

    def test_get_orders_history(self, mt5: Any) -> None:
        """Test get_orders_history() helper."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=7)
        date_to = datetime.datetime.now()

        orders = mt5.get_orders_history(date_from, date_to)
        assert orders is not None
        # Returns tuple, possibly empty

    def test_get_deals_history(self, mt5: Any) -> None:
        """Test get_deals_history() helper."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=7)
        date_to = datetime.datetime.now()

        deals = mt5.get_deals_history(date_from, date_to)
        assert deals is not None
        # Returns tuple, possibly empty

    def test_get_orders_history_by_symbol(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test filtering order history by symbol."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        orders = mt5.get_orders_history(date_from, date_to, symbol=symbol_eurusd)
        assert orders is not None

        # All orders should match symbol
        for order in orders:
            assert order.symbol == symbol_eurusd

    def test_get_deals_history_by_symbol(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test filtering deal history by symbol."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=30)
        date_to = datetime.datetime.now()

        deals = mt5.get_deals_history(date_from, date_to, symbol=symbol_eurusd)
        assert deals is not None

        # All deals should match symbol
        for deal in deals:
            assert deal.symbol == symbol_eurusd


class TestHistoryConsistency:
    """Test history data consistency."""

    def test_orders_total_matches_orders_get(self, mt5: Any) -> None:
        """Verify history_orders_total matches length of history_orders_get."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=7)
        date_to = datetime.datetime.now()

        total = mt5.history_orders_total(date_from, date_to) or 0
        orders = mt5.history_orders_get(date_from, date_to) or ()

        assert total == len(orders)

    def test_deals_total_matches_deals_get(self, mt5: Any) -> None:
        """Verify history_deals_total matches length of history_deals_get."""
        date_from = datetime.datetime.now() - datetime.timedelta(days=7)
        date_to = datetime.datetime.now()

        total = mt5.history_deals_total(date_from, date_to) or 0
        deals = mt5.history_deals_get(date_from, date_to) or ()

        assert total == len(deals)


class TestHistoryDateRanges:
    """Test history with various date ranges."""

    def test_history_today_only(self, mt5: Any) -> None:
        """Test getting today's history."""
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0)
        now = datetime.datetime.now()

        orders = mt5.history_orders_get(today, now)
        assert orders is not None or orders == ()

    def test_history_this_week(self, mt5: Any) -> None:
        """Test getting this week's history."""
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        now = datetime.datetime.now()

        deals = mt5.history_deals_get(week_ago, now)
        assert deals is not None or deals == ()

    def test_history_this_month(self, mt5: Any) -> None:
        """Test getting this month's history."""
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        now = datetime.datetime.now()

        orders = mt5.history_orders_get(month_ago, now)
        assert orders is not None or orders == ()
