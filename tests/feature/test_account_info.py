"""Feature tests for account and symbol information (Epic 3, Story 3.4).

Tests:
    - Account info retrieval
    - Symbol info retrieval
    - Symbol selection
    - Market data (ticks, prices)
    - Helper methods (get_account_balance, get_current_price, etc.)
"""

from typing import Any

import pytest

pytestmark = [pytest.mark.feature_short]


class TestAccountInfo:
    """Test account information retrieval."""

    def test_account_info_available(self, mt5: Any, account_info: Any) -> None:
        """Verify account info is available."""
        assert account_info is not None

    def test_account_has_required_fields(self, account_info: Any) -> None:
        """Verify account info has required fields."""
        required_fields = [
            "login",
            "balance",
            "equity",
            "margin",
            "margin_free",
            "currency",
            "server",
        ]
        for field in required_fields:
            assert hasattr(account_info, field), f"Missing field: {field}"

    def test_account_balance_positive(self, account_info: Any) -> None:
        """Verify DEMO account has positive balance."""
        assert account_info.balance >= 0

    def test_account_currency_valid(self, account_info: Any) -> None:
        """Verify account has valid currency."""
        assert account_info.currency in ("USD", "EUR", "GBP", "CHF", "JPY")

    def test_get_account_balance_helper(self, mt5: Any) -> None:
        """Test get_account_balance() helper method."""
        balance = mt5.get_account_balance()
        assert balance is not None
        assert isinstance(balance, float)
        assert balance >= 0

    def test_get_account_equity_helper(self, mt5: Any) -> None:
        """Test get_account_equity() helper method."""
        equity = mt5.get_account_equity()
        assert equity is not None
        assert isinstance(equity, float)

    def test_get_account_margin_helper(self, mt5: Any) -> None:
        """Test get_account_margin() helper method."""
        margin = mt5.get_account_margin()
        # May return None if no positions open
        if margin is not None:
            assert isinstance(margin, tuple)
            assert len(margin) == 3  # (margin, margin_free, margin_level)


class TestSymbolInfo:
    """Test symbol information retrieval."""

    def test_symbols_total_positive(self, mt5: Any) -> None:
        """Verify broker has symbols available."""
        total = mt5.symbols_total()
        assert total is not None
        assert total > 0

    def test_symbols_get_returns_list(self, mt5: Any) -> None:
        """Verify symbols_get returns symbol list."""
        symbols = mt5.symbols_get()
        assert symbols is not None
        assert len(symbols) > 0

    def test_symbol_eurusd_available(self, mt5: Any, symbol_eurusd: str) -> None:
        """Verify EURUSD symbol is available."""
        info = mt5.symbol_info(symbol_eurusd)
        assert info is not None
        assert info.name == symbol_eurusd

    def test_symbol_eurchf_available(self, mt5: Any, symbol_eurchf: str) -> None:
        """Verify EURCHF symbol is available."""
        info = mt5.symbol_info(symbol_eurchf)
        assert info is not None
        assert info.name == symbol_eurchf

    def test_symbol_ustec_available(self, mt5: Any, symbol_ustec: str) -> None:
        """Verify USTEC (index) symbol is available."""
        info = mt5.symbol_info(symbol_ustec)
        assert info is not None
        assert info.name == symbol_ustec

    def test_symbol_info_has_required_fields(
        self, mt5: Any, symbol_eurusd: str
    ) -> None:
        """Verify symbol info has required trading fields."""
        info = mt5.symbol_info(symbol_eurusd)
        required_fields = [
            "name",
            "bid",
            "ask",
            "spread",
            "digits",
            "volume_min",
            "volume_max",
            "volume_step",
            "trade_mode",
        ]
        for field in required_fields:
            assert hasattr(info, field), f"Missing field: {field}"

    def test_symbol_select_and_deselect(self, mt5: Any) -> None:
        """Test symbol selection in Market Watch."""
        symbol = "GBPUSD"
        # Select
        result = mt5.symbol_select(symbol, True)
        # May fail if symbol not available, that's OK
        if result:
            info = mt5.symbol_info(symbol)
            assert info is not None


class TestMarketData:
    """Test market data retrieval."""

    def test_symbol_info_tick_eurusd(self, mt5: Any, symbol_eurusd: str) -> None:
        """Verify tick data for EURUSD."""
        tick = mt5.symbol_info_tick(symbol_eurusd)
        assert tick is not None
        assert tick.bid > 0
        assert tick.ask > 0
        assert tick.ask >= tick.bid  # Ask should be >= bid

    def test_get_current_price_helper(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test get_current_price() helper method."""
        price = mt5.get_current_price(symbol_eurusd)
        assert price is not None
        assert isinstance(price, tuple)
        assert len(price) == 2  # (bid, ask)
        bid, ask = price
        assert bid > 0
        assert ask > 0
        assert ask >= bid

    def test_get_symbol_spread_helper(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test get_symbol_spread() helper method."""
        spread = mt5.get_symbol_spread(symbol_eurusd)
        assert spread is not None
        assert isinstance(spread, int)
        assert spread >= 0

    def test_tick_data_for_index(self, mt5: Any, symbol_ustec: str) -> None:
        """Verify tick data for index (USTEC)."""
        tick = mt5.symbol_info_tick(symbol_ustec)
        assert tick is not None
        assert tick.bid > 0
        assert tick.ask > 0


class TestMarketBook:
    """Test market book (DOM) functionality."""

    def test_market_book_add_and_release(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test subscribing and unsubscribing from market book."""
        # Add subscription
        result = mt5.market_book_add(symbol_eurusd)
        # May fail if not supported by broker
        if result:
            # Get book data
            book = mt5.market_book_get(symbol_eurusd)
            # Book may be empty but should not error
            assert book is not None or book == ()

            # Release subscription
            mt5.market_book_release(symbol_eurusd)


class TestCopyRates:
    """Test historical rates retrieval."""

    def test_copy_rates_from_pos(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test copying rates from position."""
        # Get last 10 M1 bars
        rates = mt5.copy_rates_from_pos(symbol_eurusd, 1, 0, 10)  # TIMEFRAME_M1=1
        assert rates is not None
        assert len(rates) > 0

    def test_copy_rates_has_ohlc(self, mt5: Any, symbol_eurusd: str) -> None:
        """Verify rates have OHLC data."""
        rates = mt5.copy_rates_from_pos(symbol_eurusd, 1, 0, 5)
        assert rates is not None
        assert len(rates) > 0

        # Check first bar has required fields
        bar = rates[0]
        assert "time" in bar.dtype.names or hasattr(bar, "time")
        assert "open" in bar.dtype.names or hasattr(bar, "open")
        assert "high" in bar.dtype.names or hasattr(bar, "high")
        assert "low" in bar.dtype.names or hasattr(bar, "low")
        assert "close" in bar.dtype.names or hasattr(bar, "close")

    def test_copy_rates_for_index(self, mt5: Any, symbol_ustec: str) -> None:
        """Test copying rates for index symbol."""
        rates = mt5.copy_rates_from_pos(symbol_ustec, 1, 0, 5)
        assert rates is not None
        assert len(rates) > 0


class TestCopyTicks:
    """Test historical ticks retrieval."""

    def test_copy_ticks_from(self, mt5: Any, symbol_eurusd: str) -> None:
        """Test copying recent ticks."""
        import datetime

        # Get ticks from last hour
        from_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        ticks = mt5.copy_ticks_from(
            symbol_eurusd, from_time, 100, 0
        )  # COPY_TICKS_ALL=0

        # May return empty if no ticks in timeframe (weekend, etc.)
        assert ticks is not None or ticks == ()
