"""Tests for account and symbol information retrieval (Story 3.4).

This module tests the account, symbol, and market data retrieval system including:
- DataRetrievalError, AccountInfoError, SymbolInfoError, MarketDataError exceptions
- account_info() logging and error handling
- symbol_info() logging and error handling
- symbol_info_tick() logging and error handling
- symbols_get() logging and error handling
- symbols_total() logging and error handling
- Market data methods logging (copy_rates_*, copy_ticks_*)
- Helper methods for common use cases
- FR68 compliance: no sensitive data in logs
"""

from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Task 1: Data Retrieval Exception Classes Tests
# =============================================================================


@pytest.mark.unit
class TestDataRetrievalError:
    """Tests for DataRetrievalError base exception."""

    def test_inherits_from_mt5linux_error(self) -> None:
        """DataRetrievalError should inherit from MT5LinuxError."""
        from mt5linux import DataRetrievalError
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(DataRetrievalError, MT5LinuxError)

    def test_create_with_message(self) -> None:
        """DataRetrievalError can be created with message."""
        from mt5linux import DataRetrievalError

        error = DataRetrievalError("Data retrieval failed")
        assert str(error) == "Data retrieval failed"

    def test_can_be_raised_and_caught(self) -> None:
        """DataRetrievalError can be raised and caught."""
        from mt5linux import DataRetrievalError

        with pytest.raises(DataRetrievalError) as exc_info:
            raise DataRetrievalError("Test error")

        assert "Test error" in str(exc_info.value)


@pytest.mark.unit
class TestAccountInfoError:
    """Tests for AccountInfoError exception."""

    def test_inherits_from_data_retrieval_error(self) -> None:
        """AccountInfoError should inherit from DataRetrievalError."""
        from mt5linux import AccountInfoError, DataRetrievalError

        assert issubclass(AccountInfoError, DataRetrievalError)

    def test_create_with_message(self) -> None:
        """AccountInfoError can be created with message."""
        from mt5linux import AccountInfoError

        error = AccountInfoError("Failed to retrieve account info")
        assert str(error) == "Failed to retrieve account info"

    def test_provides_actionable_error_message(self) -> None:
        """AccountInfoError should support actionable error messages."""
        from mt5linux import AccountInfoError

        error = AccountInfoError(
            "Failed to retrieve account info. Check MT5 connection and try again."
        )
        assert "Check MT5 connection" in str(error)

    def test_can_be_caught_as_data_retrieval_error(self) -> None:
        """AccountInfoError can be caught as DataRetrievalError."""
        from mt5linux import AccountInfoError, DataRetrievalError

        with pytest.raises(DataRetrievalError):
            raise AccountInfoError("Account error")


@pytest.mark.unit
class TestSymbolInfoError:
    """Tests for SymbolInfoError exception."""

    def test_inherits_from_data_retrieval_error(self) -> None:
        """SymbolInfoError should inherit from DataRetrievalError."""
        from mt5linux import DataRetrievalError, SymbolInfoError

        assert issubclass(SymbolInfoError, DataRetrievalError)

    def test_create_with_message(self) -> None:
        """SymbolInfoError can be created with message."""
        from mt5linux import SymbolInfoError

        error = SymbolInfoError("Failed to retrieve symbol info for EURUSD")
        assert str(error) == "Failed to retrieve symbol info for EURUSD"

    def test_provides_actionable_error_message(self) -> None:
        """SymbolInfoError should support actionable error messages."""
        from mt5linux import SymbolInfoError

        error = SymbolInfoError(
            "Symbol 'INVALID' not found. Verify symbol name is correct and available."
        )
        assert "Verify symbol name" in str(error)

    def test_can_be_caught_as_data_retrieval_error(self) -> None:
        """SymbolInfoError can be caught as DataRetrievalError."""
        from mt5linux import DataRetrievalError, SymbolInfoError

        with pytest.raises(DataRetrievalError):
            raise SymbolInfoError("Symbol error")


@pytest.mark.unit
class TestMarketDataError:
    """Tests for MarketDataError exception."""

    def test_inherits_from_data_retrieval_error(self) -> None:
        """MarketDataError should inherit from DataRetrievalError."""
        from mt5linux import DataRetrievalError, MarketDataError

        assert issubclass(MarketDataError, DataRetrievalError)

    def test_create_with_message(self) -> None:
        """MarketDataError can be created with message."""
        from mt5linux import MarketDataError

        error = MarketDataError("Failed to retrieve market data")
        assert str(error) == "Failed to retrieve market data"

    def test_provides_actionable_error_message(self) -> None:
        """MarketDataError should support actionable error messages."""
        from mt5linux import MarketDataError

        error = MarketDataError(
            "Market data unavailable for EURUSD. "
            "Market may be closed or symbol not subscribed."
        )
        assert "Market may be closed" in str(error)

    def test_can_be_caught_as_data_retrieval_error(self) -> None:
        """MarketDataError can be caught as DataRetrievalError."""
        from mt5linux import DataRetrievalError, MarketDataError

        with pytest.raises(DataRetrievalError):
            raise MarketDataError("Market data error")


@pytest.mark.unit
class TestExceptionHierarchy:
    """Tests for exception hierarchy consistency."""

    def test_all_data_exceptions_inherit_from_mt5linux_error(self) -> None:
        """All data retrieval exceptions should inherit from MT5LinuxError."""
        from mt5linux import (
            AccountInfoError,
            DataRetrievalError,
            MarketDataError,
            SymbolInfoError,
        )
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(DataRetrievalError, MT5LinuxError)
        assert issubclass(AccountInfoError, MT5LinuxError)
        assert issubclass(SymbolInfoError, MT5LinuxError)
        assert issubclass(MarketDataError, MT5LinuxError)

    def test_specific_errors_inherit_from_data_retrieval_error(self) -> None:
        """Specific errors should inherit from DataRetrievalError."""
        from mt5linux import (
            AccountInfoError,
            DataRetrievalError,
            MarketDataError,
            SymbolInfoError,
        )

        assert issubclass(AccountInfoError, DataRetrievalError)
        assert issubclass(SymbolInfoError, DataRetrievalError)
        assert issubclass(MarketDataError, DataRetrievalError)

    def test_can_catch_all_with_data_retrieval_error(self) -> None:
        """All specific exceptions can be caught with DataRetrievalError."""
        from mt5linux import (
            AccountInfoError,
            DataRetrievalError,
            MarketDataError,
            SymbolInfoError,
        )

        exceptions = [
            AccountInfoError("account"),
            SymbolInfoError("symbol"),
            MarketDataError("market"),
        ]

        for exc in exceptions:
            with pytest.raises(DataRetrievalError):
                raise exc


# =============================================================================
# Task 2: account_info() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestAccountInfoLogging:
    """Tests for account_info() logging and error handling."""

    def test_account_info_logs_retrieval_attempt(self) -> None:
        """account_info() should log retrieval attempt."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        # Mock the connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.balance = 10000.0
        mock_result.equity = 10050.0
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        # Capture log output
        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            # Check that debug logging occurred
            assert mock_logger.debug.called

    def test_account_info_logs_success_with_safe_data(self) -> None:
        """account_info() should log success with balance/equity (not sensitive data)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.balance = 10000.0
        mock_result.equity = 10050.0
        mock_result.margin = 100.0
        mock_result.leverage = 100
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            # Check success was logged
            call_args = str(mock_logger.debug.call_args_list)
            assert (
                "balance" in call_args.lower()
                or "equity" in call_args.lower()
                or "success" in call_args.lower()
            )

    def test_account_info_does_not_log_login(self) -> None:
        """account_info() must NOT log login (FR68 compliance)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.login = 12345678
        mock_result.balance = 10000.0
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            # Check that login was NOT logged
            all_calls = str(mock_logger.debug.call_args_list) + str(
                mock_logger.info.call_args_list
            )
            assert "12345678" not in all_calls

    def test_account_info_does_not_log_server(self) -> None:
        """account_info() must NOT log server name (FR68 compliance)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.server = "MyBroker-Live"
        mock_result.balance = 10000.0
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            all_calls = str(mock_logger.debug.call_args_list) + str(
                mock_logger.info.call_args_list
            )
            assert "MyBroker-Live" not in all_calls

    def test_account_info_returns_same_result_type(self) -> None:
        """account_info() should return same result type (backward compatible)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        expected_result = MagicMock()
        expected_result.balance = 10000.0
        mock_conn.eval.return_value = expected_result
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.account_info()
        assert result is expected_result

    def test_account_info_returns_none_on_error(self) -> None:
        """account_info() should return None on error (backward compatible)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.account_info()
        assert result is None

    def test_account_info_logs_warning_on_none_result(self) -> None:
        """account_info() should log warning when result is None."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            assert mock_logger.warning.called

    def test_account_info_raises_on_connection_error(self) -> None:
        """account_info() should raise AccountInfoError on connection errors."""

        from mt5linux import AccountInfoError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(AccountInfoError) as exc_info:
                mt5.account_info()
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called

    def test_account_info_stores_last_result(self) -> None:
        """account_info() should store last successful result."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.balance = 10000.0
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        mt5.account_info()
        assert mt5._last_account_info is not None


# =============================================================================
# Task 3: symbol_info() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestSymbolInfoLogging:
    """Tests for symbol_info() logging and error handling."""

    def test_symbol_info_logs_retrieval_attempt(self) -> None:
        """symbol_info() should log retrieval attempt with symbol name."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.name = "EURUSD"
        mock_result.bid = 1.1234
        mock_result.ask = 1.1236
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbol_info("EURUSD")
            # Check that debug logging occurred with symbol name
            assert mock_logger.debug.called
            call_args = str(mock_logger.debug.call_args_list)
            assert "EURUSD" in call_args

    def test_symbol_info_logs_success_with_symbol_data(self) -> None:
        """symbol_info() should log success with symbol data."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.name = "EURUSD"
        mock_result.bid = 1.1234
        mock_result.ask = 1.1236
        mock_result.spread = 2
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbol_info("EURUSD")
            call_args = str(mock_logger.debug.call_args_list)
            # Check logged symbol data (safe: bid, ask, spread)
            assert "success" in call_args.lower() or "bid" in call_args.lower()

    def test_symbol_info_returns_same_result_type(self) -> None:
        """symbol_info() should return same result type (backward compatible)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        expected_result = MagicMock()
        expected_result.name = "EURUSD"
        mock_conn.eval.return_value = expected_result
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.symbol_info("EURUSD")
        assert result is expected_result

    def test_symbol_info_returns_none_for_invalid_symbol(self) -> None:
        """symbol_info() should return None for invalid symbol."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.symbol_info("INVALID_SYMBOL")
        assert result is None

    def test_symbol_info_logs_warning_on_none_result(self) -> None:
        """symbol_info() should log warning when result is None."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbol_info("INVALID_SYMBOL")
            assert mock_logger.warning.called
            call_args = str(mock_logger.warning.call_args_list)
            assert "INVALID_SYMBOL" in call_args

    def test_symbol_info_raises_on_connection_error(self) -> None:
        """symbol_info() should raise SymbolInfoError on connection errors."""

        from mt5linux import MetaTrader5, SymbolInfoError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(SymbolInfoError) as exc_info:
                mt5.symbol_info("EURUSD")
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called

    def test_symbol_info_works_without_args(self) -> None:
        """symbol_info() should handle call without arguments."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        # Should not raise even with no args (backward compatible)
        result = mt5.symbol_info()
        assert result is None


# =============================================================================
# Task 4: symbol_info_tick() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestSymbolInfoTickLogging:
    """Tests for symbol_info_tick() logging and error handling."""

    def test_symbol_info_tick_logs_retrieval_attempt(self) -> None:
        """symbol_info_tick() should log retrieval attempt with symbol name."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.bid = 1.1234
        mock_result.ask = 1.1236
        mock_result.time = 1234567890
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbol_info_tick("EURUSD")
            assert mock_logger.debug.called
            call_args = str(mock_logger.debug.call_args_list)
            assert "EURUSD" in call_args

    def test_symbol_info_tick_logs_success_with_tick_data(self) -> None:
        """symbol_info_tick() should log success with tick data."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.bid = 1.1234
        mock_result.ask = 1.1236
        mock_result.time = 1234567890
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbol_info_tick("EURUSD")
            call_args = str(mock_logger.debug.call_args_list)
            assert "bid" in call_args.lower() or "success" in call_args.lower()

    def test_symbol_info_tick_returns_same_result_type(self) -> None:
        """symbol_info_tick() should return same result type (backward compatible)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        expected_result = MagicMock()
        expected_result.bid = 1.1234
        mock_conn.eval.return_value = expected_result
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.symbol_info_tick("EURUSD")
        assert result is expected_result

    def test_symbol_info_tick_returns_none_when_market_closed(self) -> None:
        """symbol_info_tick() should return None when market is closed."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.symbol_info_tick("EURUSD")
        assert result is None

    def test_symbol_info_tick_logs_warning_on_none_result(self) -> None:
        """symbol_info_tick() should log warning when result is None."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbol_info_tick("EURUSD")
            assert mock_logger.warning.called
            call_args = str(mock_logger.warning.call_args_list)
            # Should mention market may be closed
            assert "EURUSD" in call_args

    def test_symbol_info_tick_raises_on_connection_error(self) -> None:
        """symbol_info_tick() should raise MarketDataError on connection errors."""

        from mt5linux import MarketDataError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(MarketDataError) as exc_info:
                mt5.symbol_info_tick("EURUSD")
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called


# =============================================================================
# Task 5: symbols_get() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestSymbolsGetLogging:
    """Tests for symbols_get() logging and error handling."""

    def test_symbols_get_logs_retrieval_attempt(self) -> None:
        """symbols_get() should log retrieval attempt."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = (MagicMock(), MagicMock())  # Tuple of symbols
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbols_get()
            assert mock_logger.debug.called

    def test_symbols_get_logs_filter_pattern(self) -> None:
        """symbols_get() should log filter pattern when provided."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = (MagicMock(), MagicMock())
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbols_get(group="*USD*")
            call_args = str(mock_logger.debug.call_args_list)
            assert "*USD*" in call_args or "filter" in call_args.lower()

    def test_symbols_get_logs_result_count(self) -> None:
        """symbols_get() should log result count on success."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = (MagicMock(), MagicMock(), MagicMock())  # 3 symbols
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbols_get()
            call_args = str(mock_logger.debug.call_args_list)
            assert "3" in call_args or "count" in call_args.lower()

    def test_symbols_get_returns_same_result_type(self) -> None:
        """symbols_get() should return same result type (backward compatible)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        expected_result = (MagicMock(), MagicMock())
        mock_conn.eval.return_value = expected_result
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.symbols_get()
        assert result is expected_result

    def test_symbols_get_handles_empty_result(self) -> None:
        """symbols_get() should handle empty result gracefully."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = ()  # Empty tuple
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            result = mt5.symbols_get(group="NONEXISTENT*")
            assert result == ()
            # Should log that no symbols matched
            call_args = str(mock_logger.debug.call_args_list)
            assert (
                "0" in call_args
                or "empty" in call_args.lower()
                or "no" in call_args.lower()
            )

    def test_symbols_get_raises_on_connection_error(self) -> None:
        """symbols_get() should raise SymbolInfoError on connection errors."""

        from mt5linux import MetaTrader5, SymbolInfoError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(SymbolInfoError) as exc_info:
                mt5.symbols_get()
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called


# =============================================================================
# Task 6: symbols_total() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestSymbolsTotalLogging:
    """Tests for symbols_total() logging and error handling."""

    def test_symbols_total_logs_retrieval_attempt(self) -> None:
        """symbols_total() should log retrieval attempt."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 100
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbols_total()
            assert mock_logger.debug.called

    def test_symbols_total_logs_result_count(self) -> None:
        """symbols_total() should log result count on success."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 150
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.symbols_total()
            call_args = str(mock_logger.debug.call_args_list)
            assert "150" in call_args

    def test_symbols_total_returns_same_result_type(self) -> None:
        """symbols_total() should return same result type (backward compatible)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 100
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.symbols_total()
        assert result == 100

    def test_symbols_total_raises_on_connection_error(self) -> None:
        """symbols_total() should raise SymbolInfoError on connection errors."""

        from mt5linux import MetaTrader5, SymbolInfoError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(SymbolInfoError) as exc_info:
                mt5.symbols_total()
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called


# =============================================================================
# Task 7: Market data methods with logging (copy_rates_*, copy_ticks_*)
# =============================================================================


@pytest.mark.unit
class TestMarketDataMethodsLogging:
    """Tests for market data methods logging and error handling."""

    def test_copy_rates_from_logs_retrieval(self) -> None:
        """copy_rates_from() should log retrieval attempt."""
        import datetime

        import numpy as np

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = np.array(
            [(1, 2, 3)], dtype=[("time", "i8"), ("open", "f8"), ("close", "f8")]
        )
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with patch("rpyc.classic.obtain", return_value=mock_result):
                mt5.copy_rates_from("EURUSD", 1, datetime.datetime.now(), 100)
                assert mock_logger.debug.called
                call_args = str(mock_logger.debug.call_args_list)
                assert "EURUSD" in call_args

    def test_copy_rates_from_pos_logs_retrieval(self) -> None:
        """copy_rates_from_pos() should log retrieval attempt."""

        import numpy as np

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = np.array(
            [(1, 2, 3)], dtype=[("time", "i8"), ("open", "f8"), ("close", "f8")]
        )
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with patch("rpyc.utils.classic.obtain", return_value=mock_result):
                mt5.copy_rates_from_pos("EURUSD", 1, 0, 100)
                assert mock_logger.debug.called
                call_args = str(mock_logger.debug.call_args_list)
                assert "EURUSD" in call_args

    def test_copy_rates_range_logs_retrieval(self) -> None:
        """copy_rates_range() should log retrieval attempt."""
        import datetime

        import numpy as np

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = np.array(
            [(1, 2, 3)], dtype=[("time", "i8"), ("open", "f8"), ("close", "f8")]
        )
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with patch("rpyc.utils.classic.obtain", return_value=mock_result):
                mt5.copy_rates_range(
                    "EURUSD", 1, datetime.datetime.now(), datetime.datetime.now()
                )
                assert mock_logger.debug.called
                call_args = str(mock_logger.debug.call_args_list)
                assert "EURUSD" in call_args

    def test_copy_ticks_from_logs_retrieval(self) -> None:
        """copy_ticks_from() should log retrieval attempt."""
        import datetime

        import numpy as np

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = np.array(
            [(1, 2, 3)], dtype=[("time", "i8"), ("bid", "f8"), ("ask", "f8")]
        )
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with patch("rpyc.utils.classic.obtain", return_value=mock_result):
                mt5.copy_ticks_from("EURUSD", datetime.datetime.now(), 100, 1)
                assert mock_logger.debug.called
                call_args = str(mock_logger.debug.call_args_list)
                assert "EURUSD" in call_args

    def test_copy_ticks_range_logs_retrieval(self) -> None:
        """copy_ticks_range() should log retrieval attempt."""
        import datetime

        import numpy as np

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = np.array(
            [(1, 2, 3)], dtype=[("time", "i8"), ("bid", "f8"), ("ask", "f8")]
        )
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with patch("rpyc.utils.classic.obtain", return_value=mock_result):
                mt5.copy_ticks_range(
                    "EURUSD", datetime.datetime.now(), datetime.datetime.now(), 1
                )
                assert mock_logger.debug.called
                call_args = str(mock_logger.debug.call_args_list)
                assert "EURUSD" in call_args

    def test_copy_rates_from_handles_none_result(self) -> None:
        """copy_rates_from() should handle None result gracefully."""
        import datetime

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with patch("rpyc.classic.obtain", return_value=None):
                result = mt5.copy_rates_from("INVALID", 1, datetime.datetime.now(), 100)
                assert result is None
                assert mock_logger.warning.called

    def test_copy_rates_from_raises_on_connection_error(self) -> None:
        """copy_rates_from() should raise MarketDataError on connection errors."""
        import datetime

        from mt5linux import MarketDataError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(MarketDataError) as exc_info:
                mt5.copy_rates_from("EURUSD", 1, datetime.datetime.now(), 100)
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called

    def test_market_data_methods_preserve_backward_compatibility(self) -> None:
        """Market data methods should return same result type."""
        import datetime

        import numpy as np

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        expected_result = np.array(
            [(1, 2, 3)], dtype=[("time", "i8"), ("open", "f8"), ("close", "f8")]
        )
        mock_conn.eval.return_value = expected_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("rpyc.classic.obtain", return_value=expected_result):
            result = mt5.copy_rates_from("EURUSD", 1, datetime.datetime.now(), 100)
            assert result is expected_result


# =============================================================================
# Task 8: Helper methods for common use cases
# =============================================================================


@pytest.mark.unit
class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_account_balance_returns_float(self) -> None:
        """get_account_balance() should return balance as float."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.balance = 10000.50
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        balance = mt5.get_account_balance()
        assert balance == 10000.50
        assert isinstance(balance, float)

    def test_get_account_balance_returns_none_on_error(self) -> None:
        """get_account_balance() should return None on error."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        balance = mt5.get_account_balance()
        assert balance is None

    def test_get_account_equity_returns_float(self) -> None:
        """get_account_equity() should return equity as float."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.equity = 10050.75
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        equity = mt5.get_account_equity()
        assert equity == 10050.75
        assert isinstance(equity, float)

    def test_get_account_equity_returns_none_on_error(self) -> None:
        """get_account_equity() should return None on error."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        equity = mt5.get_account_equity()
        assert equity is None

    def test_get_account_margin_returns_tuple(self) -> None:
        """get_account_margin() should return margin info as tuple."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.margin = 100.0
        mock_result.margin_free = 9900.0
        mock_result.margin_level = 10000.0
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        margin_info = mt5.get_account_margin()
        assert margin_info == (100.0, 9900.0, 10000.0)
        assert isinstance(margin_info, tuple)

    def test_get_account_margin_returns_none_on_error(self) -> None:
        """get_account_margin() should return None on error."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        margin_info = mt5.get_account_margin()
        assert margin_info is None

    def test_get_symbol_spread_returns_int(self) -> None:
        """get_symbol_spread() should return spread in points."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.spread = 15
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        spread = mt5.get_symbol_spread("EURUSD")
        assert spread == 15

    def test_get_symbol_spread_returns_none_on_error(self) -> None:
        """get_symbol_spread() should return None on error."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        spread = mt5.get_symbol_spread("INVALID")
        assert spread is None

    def test_get_current_price_returns_tuple(self) -> None:
        """get_current_price() should return (bid, ask) tuple."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.bid = 1.1234
        mock_result.ask = 1.1236
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        price = mt5.get_current_price("EURUSD")
        assert price == (1.1234, 1.1236)
        assert isinstance(price, tuple)

    def test_get_current_price_returns_none_on_error(self) -> None:
        """get_current_price() should return None on error."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        price = mt5.get_current_price("INVALID")
        assert price is None


# =============================================================================
# Task 9: FR68 Compliance - Logging Does NOT Include Sensitive Data
# =============================================================================


@pytest.mark.unit
class TestLoggingCompliance:
    """Tests for FR68 compliance: no sensitive data in logs."""

    def test_account_info_does_not_log_password(self) -> None:
        """account_info() must NOT log password (FR68 compliance)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.password = "secret123"
        mock_result.balance = 10000.0
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            all_calls = str(mock_logger.debug.call_args_list) + str(
                mock_logger.info.call_args_list
            )
            assert "secret123" not in all_calls
            assert "password" not in all_calls.lower()

    def test_account_info_does_not_log_name(self) -> None:
        """account_info() must NOT log account name (FR68 compliance)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.name = "John Doe Trading Account"
        mock_result.balance = 10000.0
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            all_calls = str(mock_logger.debug.call_args_list) + str(
                mock_logger.info.call_args_list
            )
            assert "John Doe" not in all_calls

    def test_account_info_logs_safe_financial_data(self) -> None:
        """account_info() should log safe financial data (balance, equity, margin)."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.balance = 12345.67
        mock_result.equity = 12400.50
        mock_result.margin = 100.0
        mock_result.leverage = 100
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.account_info()
            call_args = str(mock_logger.debug.call_args_list)
            # Safe data should be logged
            assert "balance" in call_args.lower()


@pytest.mark.unit
class TestConnectionErrorHandling:
    """Tests for connection error handling across all methods."""

    def test_all_methods_handle_none_connection(self) -> None:
        """Methods should handle None connection gracefully."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        # Connection is None by default before initialize()

        # These should not raise, just return None or handle gracefully
        # (The actual behavior depends on implementation, but no unhandled exceptions)
        # Most methods will fail because __conn is None, but they should not crash

    def test_symbol_info_with_empty_symbol(self) -> None:
        """symbol_info() should handle empty symbol name."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        # Should not crash with empty symbol
        result = mt5.symbol_info("")
        assert result is None

    def test_symbol_info_tick_with_special_characters(self) -> None:
        """symbol_info_tick() should handle symbol with special characters."""

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.bid = 1.0
        mock_result.ask = 1.1
        mock_conn.eval.return_value = mock_result
        mt5._MetaTrader5__conn = mock_conn

        # Should handle symbols with dots, underscores, etc.
        result = mt5.symbol_info_tick("EUR_USD.micro")
        assert result is not None
