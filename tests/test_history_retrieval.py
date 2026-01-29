"""Tests for trading history retrieval (Story 3.6).

This module tests the trading history retrieval system including:
- HistoryError, HistoryRetrievalError exceptions
- history_orders_total() logging and error handling
- history_orders_get() logging and error handling
- history_deals_total() logging and error handling
- history_deals_get() logging and error handling
- get_orders_history() helper method
- get_deals_history() helper method
- get_position_history() helper method
- calculate_position_profit() helper method
- FR68 compliance: no sensitive data in logs
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Task 1: History Retrieval Exception Classes Tests
# =============================================================================


@pytest.mark.unit
class TestHistoryError:
    """Tests for HistoryError base exception."""

    def test_inherits_from_mt5linux_error(self) -> None:
        """HistoryError should inherit from MT5LinuxError."""
        from mt5linux import HistoryError
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(HistoryError, MT5LinuxError)

    def test_create_with_message(self) -> None:
        """HistoryError can be created with message."""
        from mt5linux import HistoryError

        error = HistoryError("History operation failed")
        assert str(error) == "History operation failed"

    def test_can_be_raised_and_caught(self) -> None:
        """HistoryError can be raised and caught."""
        from mt5linux import HistoryError

        with pytest.raises(HistoryError) as exc_info:
            raise HistoryError("Test error")

        assert "Test error" in str(exc_info.value)

    def test_provides_actionable_error_message(self) -> None:
        """HistoryError should support actionable error messages."""
        from mt5linux import HistoryError

        error = HistoryError(
            "History retrieval failed. Check MT5 connection and date range."
        )
        assert "Check MT5 connection" in str(error)


@pytest.mark.unit
class TestHistoryRetrievalError:
    """Tests for HistoryRetrievalError exception."""

    def test_inherits_from_history_error(self) -> None:
        """HistoryRetrievalError should inherit from HistoryError."""
        from mt5linux import HistoryError, HistoryRetrievalError

        assert issubclass(HistoryRetrievalError, HistoryError)

    def test_create_with_message(self) -> None:
        """HistoryRetrievalError can be created with message."""
        from mt5linux import HistoryRetrievalError

        error = HistoryRetrievalError("Failed to retrieve order history")
        assert str(error) == "Failed to retrieve order history"

    def test_provides_actionable_error_message_with_context(self) -> None:
        """HistoryRetrievalError should support actionable error messages with context."""
        from mt5linux import HistoryRetrievalError

        error = HistoryRetrievalError(
            "Failed to retrieve history for date range 2024-01-01 to 2024-01-31. "
            "Check connection and retry."
        )
        assert "date range" in str(error)
        assert "Check connection" in str(error)

    def test_can_be_caught_as_history_error(self) -> None:
        """HistoryRetrievalError can be caught as HistoryError."""
        from mt5linux import HistoryError, HistoryRetrievalError

        with pytest.raises(HistoryError):
            raise HistoryRetrievalError("Retrieval error")


@pytest.mark.unit
class TestHistoryExceptionHierarchy:
    """Tests for history exception hierarchy consistency."""

    def test_all_history_exceptions_inherit_from_mt5linux_error(self) -> None:
        """All history exceptions should inherit from MT5LinuxError."""
        from mt5linux import HistoryError, HistoryRetrievalError
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(HistoryError, MT5LinuxError)
        assert issubclass(HistoryRetrievalError, MT5LinuxError)

    def test_specific_errors_inherit_from_history_error(self) -> None:
        """Specific errors should inherit from HistoryError."""
        from mt5linux import HistoryError, HistoryRetrievalError

        assert issubclass(HistoryRetrievalError, HistoryError)

    def test_can_catch_all_with_history_error(self) -> None:
        """All specific exceptions can be caught with HistoryError."""
        from mt5linux import HistoryError, HistoryRetrievalError

        exceptions = [
            HistoryRetrievalError("retrieval"),
        ]

        for exc in exceptions:
            with pytest.raises(HistoryError):
                raise exc


# =============================================================================
# Task 2: history_orders_total() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestHistoryOrdersTotalLogging:
    """Tests for history_orders_total() logging and error handling."""

    def _create_mock_mt5(self, return_value):
        """Helper to create MT5 instance with mocked connection."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = return_value
        mt5._MetaTrader5__conn = mock_conn
        return mt5, mock_conn

    def test_history_orders_total_logs_retrieval_attempt(self) -> None:
        """history_orders_total() should log retrieval attempt."""
        mt5, _ = self._create_mock_mt5(5)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_orders_total(date_from, date_to)
            assert mock_logger.debug.called

    def test_history_orders_total_logs_date_range(self) -> None:
        """history_orders_total() should log date range."""
        mt5, _ = self._create_mock_mt5(10)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_orders_total(date_from, date_to)
            call_args = str(mock_logger.debug.call_args_list)
            # Should log the date range information
            assert "date" in call_args.lower() or "2024" in call_args

    def test_history_orders_total_logs_count_returned(self) -> None:
        """history_orders_total() should log count returned."""
        mt5, _ = self._create_mock_mt5(42)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_orders_total(date_from, date_to)
            call_args = str(mock_logger.debug.call_args_list)
            assert "42" in call_args or "count" in call_args.lower()

    def test_history_orders_total_returns_same_result_type(self) -> None:
        """history_orders_total() should return same result type (backward compatible)."""
        mt5, _ = self._create_mock_mt5(5)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_orders_total(date_from, date_to)
        assert result == 5
        assert isinstance(result, int)

    def test_history_orders_total_raises_on_connection_error(self) -> None:
        """history_orders_total() should raise HistoryError on connection errors."""
        from mt5linux import HistoryError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(HistoryError) as exc_info:
                mt5.history_orders_total(date_from, date_to)
            assert (
                "Connection" in str(exc_info.value)
                or "connection" in str(exc_info.value).lower()
            )
            assert mock_logger.warning.called

    def test_history_orders_total_handles_zero_result(self) -> None:
        """history_orders_total() should handle zero orders gracefully."""
        mt5, _ = self._create_mock_mt5(0)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_orders_total(date_from, date_to)
        assert result == 0

    def test_history_orders_total_validates_date_range(self) -> None:
        """history_orders_total() should validate date_from < date_to."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 31)  # Later date
        date_to = datetime(2024, 1, 1)  # Earlier date

        with pytest.raises(HistoryRetrievalError) as exc_info:
            mt5.history_orders_total(date_from, date_to)
        assert "date" in str(exc_info.value).lower()


# =============================================================================
# Task 3: history_orders_get() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestHistoryOrdersGetLogging:
    """Tests for history_orders_get() logging and error handling."""

    def _create_mock_mt5(self, return_value):
        """Helper to create MT5 instance with mocked connection."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = return_value
        mt5._MetaTrader5__conn = mock_conn
        return mt5, mock_conn

    def test_history_orders_get_logs_retrieval_attempt(self) -> None:
        """history_orders_get() should log retrieval attempt."""
        mock_order = MagicMock()
        mock_order.ticket = 12345
        mt5, _ = self._create_mock_mt5((mock_order,))

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_orders_get(date_from, date_to)
            assert mock_logger.debug.called

    def test_history_orders_get_logs_date_range_and_filters(self) -> None:
        """history_orders_get() should log date range and filters applied."""
        mock_order = MagicMock()
        mt5, _ = self._create_mock_mt5((mock_order,))

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_orders_get(date_from, date_to, group="*EURUSD*")
            call_args = str(mock_logger.debug.call_args_list)
            # Should log filter info
            assert "EURUSD" in call_args or "group" in call_args.lower()

    def test_history_orders_get_logs_order_count(self) -> None:
        """history_orders_get() should log order count retrieved."""
        mock_orders = (MagicMock(), MagicMock(), MagicMock())
        mt5, _ = self._create_mock_mt5(mock_orders)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_orders_get(date_from, date_to)
            call_args = str(mock_logger.debug.call_args_list)
            assert "3" in call_args or "count" in call_args.lower()

    def test_history_orders_get_returns_same_result_type(self) -> None:
        """history_orders_get() should return same result type (backward compatible)."""
        expected_result = (MagicMock(), MagicMock())
        mt5, _ = self._create_mock_mt5(expected_result)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_orders_get(date_from, date_to)
        assert result is expected_result

    def test_history_orders_get_handles_empty_result(self) -> None:
        """history_orders_get() should handle empty result gracefully (not an error)."""
        mt5, _ = self._create_mock_mt5(())  # Empty tuple

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger"):
            result = mt5.history_orders_get(date_from, date_to, group="*NONEXISTENT*")
            assert result == ()

    def test_history_orders_get_handles_none_result(self) -> None:
        """history_orders_get() should handle None result (backward compatible)."""
        mt5, _ = self._create_mock_mt5(None)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_orders_get(date_from, date_to)
        assert result is None

    def test_history_orders_get_raises_on_connection_error(self) -> None:
        """history_orders_get() should raise HistoryRetrievalError on connection errors."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(HistoryRetrievalError) as exc_info:
                mt5.history_orders_get(date_from, date_to)
            assert (
                "Connection" in str(exc_info.value)
                or "connection" in str(exc_info.value).lower()
            )
            assert mock_logger.warning.called

    def test_history_orders_get_with_ticket_filter(self) -> None:
        """history_orders_get() should work with ticket filter."""
        mock_order = MagicMock()
        mock_order.ticket = 12345
        mt5, _ = self._create_mock_mt5((mock_order,))

        with patch("mt5linux.logger") as mock_logger:
            result = mt5.history_orders_get(ticket=12345)
            assert result == (mock_order,)
            call_args = str(mock_logger.debug.call_args_list)
            assert "12345" in call_args

    def test_history_orders_get_with_position_filter(self) -> None:
        """history_orders_get() should work with position filter."""
        mock_order = MagicMock()
        mt5, _ = self._create_mock_mt5((mock_order,))

        with patch("mt5linux.logger") as mock_logger:
            result = mt5.history_orders_get(position=99999)
            assert len(result) == 1
            call_args = str(mock_logger.debug.call_args_list)
            assert "99999" in call_args or "position" in call_args.lower()


# =============================================================================
# Task 4: history_deals_total() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestHistoryDealsTotalLogging:
    """Tests for history_deals_total() logging and error handling."""

    def _create_mock_mt5(self, return_value):
        """Helper to create MT5 instance with mocked connection."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = return_value
        mt5._MetaTrader5__conn = mock_conn
        return mt5, mock_conn

    def test_history_deals_total_logs_retrieval_attempt(self) -> None:
        """history_deals_total() should log retrieval attempt."""
        mt5, _ = self._create_mock_mt5(5)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_deals_total(date_from, date_to)
            assert mock_logger.debug.called

    def test_history_deals_total_logs_date_range(self) -> None:
        """history_deals_total() should log date range."""
        mt5, _ = self._create_mock_mt5(10)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_deals_total(date_from, date_to)
            call_args = str(mock_logger.debug.call_args_list)
            assert "date" in call_args.lower() or "2024" in call_args

    def test_history_deals_total_logs_count_returned(self) -> None:
        """history_deals_total() should log count returned."""
        mt5, _ = self._create_mock_mt5(42)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_deals_total(date_from, date_to)
            call_args = str(mock_logger.debug.call_args_list)
            assert "42" in call_args or "count" in call_args.lower()

    def test_history_deals_total_returns_same_result_type(self) -> None:
        """history_deals_total() should return same result type (backward compatible)."""
        mt5, _ = self._create_mock_mt5(5)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_deals_total(date_from, date_to)
        assert result == 5
        assert isinstance(result, int)

    def test_history_deals_total_raises_on_connection_error(self) -> None:
        """history_deals_total() should raise HistoryError on connection errors."""
        from mt5linux import HistoryError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(HistoryError) as exc_info:
                mt5.history_deals_total(date_from, date_to)
            assert (
                "Connection" in str(exc_info.value)
                or "connection" in str(exc_info.value).lower()
            )
            assert mock_logger.warning.called

    def test_history_deals_total_handles_zero_result(self) -> None:
        """history_deals_total() should handle zero deals gracefully."""
        mt5, _ = self._create_mock_mt5(0)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_deals_total(date_from, date_to)
        assert result == 0

    def test_history_deals_total_validates_date_range(self) -> None:
        """history_deals_total() should validate date_from < date_to."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 31)  # Later date
        date_to = datetime(2024, 1, 1)  # Earlier date

        with pytest.raises(HistoryRetrievalError) as exc_info:
            mt5.history_deals_total(date_from, date_to)
        assert "date" in str(exc_info.value).lower()


# =============================================================================
# Task 5: history_deals_get() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestHistoryDealsGetLogging:
    """Tests for history_deals_get() logging and error handling."""

    def _create_mock_mt5(self, return_value):
        """Helper to create MT5 instance with mocked connection."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = return_value
        mt5._MetaTrader5__conn = mock_conn
        return mt5, mock_conn

    def test_history_deals_get_logs_retrieval_attempt(self) -> None:
        """history_deals_get() should log retrieval attempt."""
        mock_deal = MagicMock()
        mock_deal.ticket = 12345
        mt5, _ = self._create_mock_mt5((mock_deal,))

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_deals_get(date_from, date_to)
            assert mock_logger.debug.called

    def test_history_deals_get_logs_date_range_and_filters(self) -> None:
        """history_deals_get() should log date range and filters applied."""
        mock_deal = MagicMock()
        mt5, _ = self._create_mock_mt5((mock_deal,))

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_deals_get(date_from, date_to, group="*EURUSD*")
            call_args = str(mock_logger.debug.call_args_list)
            assert "EURUSD" in call_args or "group" in call_args.lower()

    def test_history_deals_get_logs_deal_count(self) -> None:
        """history_deals_get() should log deal count retrieved."""
        mock_deals = (MagicMock(), MagicMock(), MagicMock())
        mt5, _ = self._create_mock_mt5(mock_deals)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_deals_get(date_from, date_to)
            call_args = str(mock_logger.debug.call_args_list)
            assert "3" in call_args or "count" in call_args.lower()

    def test_history_deals_get_returns_same_result_type(self) -> None:
        """history_deals_get() should return same result type (backward compatible)."""
        expected_result = (MagicMock(), MagicMock())
        mt5, _ = self._create_mock_mt5(expected_result)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_deals_get(date_from, date_to)
        assert result is expected_result

    def test_history_deals_get_handles_empty_result(self) -> None:
        """history_deals_get() should handle empty result gracefully (not an error)."""
        mt5, _ = self._create_mock_mt5(())  # Empty tuple

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger"):
            result = mt5.history_deals_get(date_from, date_to, group="*NONEXISTENT*")
            assert result == ()

    def test_history_deals_get_handles_none_result(self) -> None:
        """history_deals_get() should handle None result (backward compatible)."""
        mt5, _ = self._create_mock_mt5(None)

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        result = mt5.history_deals_get(date_from, date_to)
        assert result is None

    def test_history_deals_get_raises_on_connection_error(self) -> None:
        """history_deals_get() should raise HistoryRetrievalError on connection errors."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(HistoryRetrievalError) as exc_info:
                mt5.history_deals_get(date_from, date_to)
            assert (
                "Connection" in str(exc_info.value)
                or "connection" in str(exc_info.value).lower()
            )
            assert mock_logger.warning.called

    def test_history_deals_get_with_position_filter(self) -> None:
        """history_deals_get() should work with position filter."""
        mock_deal = MagicMock()
        mt5, _ = self._create_mock_mt5((mock_deal,))

        with patch("mt5linux.logger") as mock_logger:
            result = mt5.history_deals_get(position=99999)
            assert len(result) == 1
            call_args = str(mock_logger.debug.call_args_list)
            assert "99999" in call_args or "position" in call_args.lower()


# =============================================================================
# Task 6: get_orders_history() helper method
# =============================================================================


@pytest.mark.unit
class TestGetOrdersHistory:
    """Tests for get_orders_history() helper method."""

    def test_get_orders_history_returns_orders(self) -> None:
        """get_orders_history() should return orders for date range."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_order1 = MagicMock()
        mock_order2 = MagicMock()

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.return_value = (mock_order1, mock_order2)

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            result = mt5.get_orders_history(date_from, date_to)

            assert len(result) == 2
            mock_history_get.assert_called_once()

    def test_get_orders_history_with_symbol_filter(self) -> None:
        """get_orders_history() should apply symbol filter as group."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.return_value = ()

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            mt5.get_orders_history(date_from, date_to, symbol="EURUSD")

            # Symbol should be converted to group filter pattern
            call_kwargs = mock_history_get.call_args.kwargs
            assert "group" in call_kwargs
            assert "EURUSD" in call_kwargs["group"]

    def test_get_orders_history_validates_date_range(self) -> None:
        """get_orders_history() should raise on invalid date range."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 31)  # Later
        date_to = datetime(2024, 1, 1)  # Earlier

        with pytest.raises(HistoryRetrievalError) as exc_info:
            mt5.get_orders_history(date_from, date_to)

        assert "date" in str(exc_info.value).lower()

    def test_get_orders_history_returns_empty_tuple_not_none(self) -> None:
        """get_orders_history() should return empty tuple, never None."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.return_value = None

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            result = mt5.get_orders_history(date_from, date_to)

            assert result == ()
            assert result is not None

    def test_get_orders_history_raises_on_failure(self) -> None:
        """get_orders_history() should raise HistoryRetrievalError on failure."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.side_effect = HistoryRetrievalError("Connection failed")

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            with pytest.raises(HistoryRetrievalError):
                mt5.get_orders_history(date_from, date_to)

    def test_get_orders_history_logs_retrieval(self) -> None:
        """get_orders_history() should log retrieval info (FR68 compliant)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.return_value = (MagicMock(),)

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            with patch("mt5linux.logger") as mock_logger:
                mt5.get_orders_history(date_from, date_to)
                assert mock_logger.debug.called

    def test_get_orders_history_equal_dates_returns_empty(self) -> None:
        """get_orders_history() with equal dates should return empty, not error."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.return_value = ()

            same_date = datetime(2024, 1, 15)

            # Equal dates should be allowed and return empty tuple
            result = mt5.get_orders_history(same_date, same_date)
            assert result == ()
            mock_history_get.assert_called_once()


# =============================================================================
# Task 7: get_deals_history() helper method
# =============================================================================


@pytest.mark.unit
class TestGetDealsHistory:
    """Tests for get_deals_history() helper method."""

    def test_get_deals_history_returns_deals(self) -> None:
        """get_deals_history() should return deals for date range."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_deal1 = MagicMock()
        mock_deal2 = MagicMock()

        with patch.object(mt5, "history_deals_get") as mock_history_get:
            mock_history_get.return_value = (mock_deal1, mock_deal2)

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            result = mt5.get_deals_history(date_from, date_to)

            assert len(result) == 2
            mock_history_get.assert_called_once()

    def test_get_deals_history_with_symbol_filter(self) -> None:
        """get_deals_history() should apply symbol filter as group."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_deals_get") as mock_history_get:
            mock_history_get.return_value = ()

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            mt5.get_deals_history(date_from, date_to, symbol="EURUSD")

            call_kwargs = mock_history_get.call_args.kwargs
            assert "group" in call_kwargs
            assert "EURUSD" in call_kwargs["group"]

    def test_get_deals_history_validates_date_range(self) -> None:
        """get_deals_history() should raise on invalid date range."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        date_from = datetime(2024, 1, 31)
        date_to = datetime(2024, 1, 1)

        with pytest.raises(HistoryRetrievalError) as exc_info:
            mt5.get_deals_history(date_from, date_to)

        assert "date" in str(exc_info.value).lower()

    def test_get_deals_history_returns_empty_tuple_not_none(self) -> None:
        """get_deals_history() should return empty tuple, never None."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_deals_get") as mock_history_get:
            mock_history_get.return_value = None

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            result = mt5.get_deals_history(date_from, date_to)

            assert result == ()
            assert result is not None

    def test_get_deals_history_raises_on_failure(self) -> None:
        """get_deals_history() should raise HistoryRetrievalError on failure."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_deals_get") as mock_history_get:
            mock_history_get.side_effect = HistoryRetrievalError("Connection failed")

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            with pytest.raises(HistoryRetrievalError):
                mt5.get_deals_history(date_from, date_to)

    def test_get_deals_history_logs_retrieval(self) -> None:
        """get_deals_history() should log retrieval info (FR68 compliant)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_deals_get") as mock_history_get:
            mock_history_get.return_value = (MagicMock(),)

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            with patch("mt5linux.logger") as mock_logger:
                mt5.get_deals_history(date_from, date_to)
                assert mock_logger.debug.called

    def test_get_deals_history_equal_dates_returns_empty(self) -> None:
        """get_deals_history() with equal dates should return empty, not error."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_deals_get") as mock_history_get:
            mock_history_get.return_value = ()

            same_date = datetime(2024, 1, 15)

            # Equal dates should be allowed and return empty tuple
            result = mt5.get_deals_history(same_date, same_date)
            assert result == ()
            mock_history_get.assert_called_once()


# =============================================================================
# Task 8: get_position_history() helper method
# =============================================================================


@pytest.mark.unit
class TestGetPositionHistory:
    """Tests for get_position_history() helper method."""

    def test_get_position_history_returns_orders_and_deals(self) -> None:
        """get_position_history() should return dict with orders and deals."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_order = MagicMock()
        mock_deal = MagicMock()

        with patch.object(mt5, "history_orders_get") as mock_orders_get:
            with patch.object(mt5, "history_deals_get") as mock_deals_get:
                mock_orders_get.return_value = (mock_order,)
                mock_deals_get.return_value = (mock_deal,)

                result = mt5.get_position_history(12345)

                assert "orders" in result
                assert "deals" in result
                assert len(result["orders"]) == 1
                assert len(result["deals"]) == 1
                mock_orders_get.assert_called_once_with(position=12345)
                mock_deals_get.assert_called_once_with(position=12345)

    def test_get_position_history_raises_if_not_found(self) -> None:
        """get_position_history() should raise if no history found for ticket."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_orders_get:
            with patch.object(mt5, "history_deals_get") as mock_deals_get:
                mock_orders_get.return_value = ()
                mock_deals_get.return_value = ()

                with pytest.raises(HistoryRetrievalError) as exc_info:
                    mt5.get_position_history(99999)

                assert "99999" in str(exc_info.value)
                assert "not found" in str(exc_info.value).lower()

    def test_get_position_history_logs_warning_when_not_found(self) -> None:
        """get_position_history() should log warning before raising when not found."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_orders_get:
            with patch.object(mt5, "history_deals_get") as mock_deals_get:
                mock_orders_get.return_value = ()
                mock_deals_get.return_value = ()

                with patch("mt5linux.logger") as mock_logger:
                    with pytest.raises(HistoryRetrievalError):
                        mt5.get_position_history(99999)

                    # Should log warning before raising
                    assert mock_logger.warning.called
                    call_args = str(mock_logger.warning.call_args)
                    assert "99999" in call_args or "not found" in call_args.lower()

    def test_get_position_history_logs_retrieval(self) -> None:
        """get_position_history() should log retrieval with position ticket."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_orders_get:
            with patch.object(mt5, "history_deals_get") as mock_deals_get:
                mock_orders_get.return_value = (MagicMock(),)
                mock_deals_get.return_value = (MagicMock(),)

                with patch("mt5linux.logger") as mock_logger:
                    mt5.get_position_history(12345)
                    call_args = str(mock_logger.debug.call_args_list)
                    assert "12345" in call_args

    def test_get_position_history_handles_none_results(self) -> None:
        """get_position_history() should handle None results from underlying methods."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_orders_get:
            with patch.object(mt5, "history_deals_get") as mock_deals_get:
                mock_orders_get.return_value = None
                mock_deals_get.return_value = None

                # Should raise because no history found
                with pytest.raises(HistoryRetrievalError):
                    mt5.get_position_history(99999)


# =============================================================================
# Task 9: calculate_position_profit() helper method
# =============================================================================


@pytest.mark.unit
class TestCalculatePositionProfit:
    """Tests for calculate_position_profit() helper method."""

    def test_calculate_position_profit_returns_result(self) -> None:
        """calculate_position_profit() should return PositionProfitResult."""
        from mt5linux import MetaTrader5, PositionProfitResult

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_deal1 = MagicMock()
        mock_deal1.profit = 100.0
        mock_deal1.commission = -2.0
        mock_deal1.swap = -1.5

        mock_deal2 = MagicMock()
        mock_deal2.profit = -50.0
        mock_deal2.commission = -2.0
        mock_deal2.swap = -0.5

        with patch.object(mt5, "history_deals_get") as mock_deals_get:
            mock_deals_get.return_value = (mock_deal1, mock_deal2)

            result = mt5.calculate_position_profit(12345)

            assert isinstance(result, PositionProfitResult)
            assert result.ticket == 12345
            assert result.profit == 50.0  # 100 - 50
            assert result.commission == -4.0  # -2 + -2
            assert result.swap == -2.0  # -1.5 + -0.5
            assert result.total == 44.0  # 50 - 4 - 2

    def test_calculate_position_profit_raises_if_no_deals(self) -> None:
        """calculate_position_profit() should raise if no deals found."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_deals_get") as mock_deals_get:
            mock_deals_get.return_value = ()

            with pytest.raises(HistoryRetrievalError) as exc_info:
                mt5.calculate_position_profit(99999)

            assert "99999" in str(exc_info.value)

    def test_calculate_position_profit_handles_missing_fields(self) -> None:
        """calculate_position_profit() should handle deals with missing optional fields."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_deal = MagicMock()
        mock_deal.profit = 100.0
        mock_deal.commission = 0.0  # Some deals might not have commission
        mock_deal.swap = 0.0

        with patch.object(mt5, "history_deals_get") as mock_deals_get:
            mock_deals_get.return_value = (mock_deal,)

            result = mt5.calculate_position_profit(12345)

            assert result.profit == 100.0
            assert result.commission == 0.0
            assert result.swap == 0.0
            assert result.total == 100.0

    def test_calculate_position_profit_handles_truly_missing_attributes(self) -> None:
        """calculate_position_profit() should handle deals without swap/commission attributes."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        # Create a mock that doesn't have swap attribute at all
        mock_deal = MagicMock(spec=["profit"])
        mock_deal.profit = 50.0
        # Explicitly remove commission and swap to simulate missing attributes
        del mock_deal.commission
        del mock_deal.swap

        with patch.object(mt5, "history_deals_get") as mock_deals_get:
            mock_deals_get.return_value = (mock_deal,)

            result = mt5.calculate_position_profit(12345)

            # getattr with default should handle missing attributes
            assert result.profit == 50.0
            assert result.commission == 0.0  # Default when missing
            assert result.swap == 0.0  # Default when missing
            assert result.total == 50.0

    def test_calculate_position_profit_logs_calculation(self) -> None:
        """calculate_position_profit() should log calculation with ticket."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_deal = MagicMock()
        mock_deal.profit = 100.0
        mock_deal.commission = -2.0
        mock_deal.swap = -1.0

        with patch.object(mt5, "history_deals_get") as mock_deals_get:
            mock_deals_get.return_value = (mock_deal,)

            with patch("mt5linux.logger") as mock_logger:
                mt5.calculate_position_profit(12345)
                call_args = str(mock_logger.debug.call_args_list)
                assert "12345" in call_args


@pytest.mark.unit
class TestPositionProfitResult:
    """Tests for PositionProfitResult dataclass."""

    def test_position_profit_result_is_frozen(self) -> None:
        """PositionProfitResult should be immutable (frozen=True)."""
        from mt5linux import PositionProfitResult

        result = PositionProfitResult(
            ticket=12345, profit=100.0, commission=-2.0, swap=-1.0, total=97.0
        )

        with pytest.raises(AttributeError):
            result.profit = 200.0  # type: ignore

    def test_position_profit_result_has_slots(self) -> None:
        """PositionProfitResult should use slots for memory efficiency."""
        from mt5linux import PositionProfitResult

        result = PositionProfitResult(
            ticket=12345, profit=100.0, commission=-2.0, swap=-1.0, total=97.0
        )

        # Slots means no __dict__
        assert not hasattr(result, "__dict__")


# =============================================================================
# Task 10: FR68 Compliance - Logging Does NOT Include Sensitive Data
# =============================================================================


@pytest.mark.unit
class TestHistoryLoggingCompliance:
    """Tests for FR68 compliance: no sensitive data in history logs."""

    def _create_mock_mt5(self, return_value):
        """Helper to create MT5 instance with mocked connection."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = return_value
        mt5._MetaTrader5__conn = mock_conn
        return mt5, mock_conn

    def test_history_orders_get_does_not_log_login(self) -> None:
        """history_orders_get() must NOT log login (FR68 compliance)."""
        mock_order = MagicMock()
        mock_order.ticket = 12345
        mt5, _ = self._create_mock_mt5((mock_order,))

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_orders_get(date_from, date_to)
            all_calls = str(mock_logger.debug.call_args_list) + str(
                mock_logger.info.call_args_list
            )
            assert "password" not in all_calls.lower()
            assert "login" not in all_calls.lower()
            assert "server" not in all_calls.lower()

    def test_history_deals_get_does_not_log_account(self) -> None:
        """history_deals_get() must NOT log account info (FR68 compliance)."""
        mock_deal = MagicMock()
        mock_deal.ticket = 12345
        mt5, _ = self._create_mock_mt5((mock_deal,))

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        with patch("mt5linux.logger") as mock_logger:
            mt5.history_deals_get(date_from, date_to)
            all_calls = str(mock_logger.debug.call_args_list) + str(
                mock_logger.info.call_args_list
            )
            assert "password" not in all_calls.lower()
            assert "login" not in all_calls.lower()

    def test_get_orders_history_logs_safe_data(self) -> None:
        """get_orders_history() should log date range, not sensitive data."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.return_value = ()

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 1, 31)

            with patch("mt5linux.logger") as mock_logger:
                mt5.get_orders_history(date_from, date_to)
                all_calls = str(mock_logger.debug.call_args_list)
                # Should log date info
                assert "date" in all_calls.lower() or "2024" in all_calls
                # No sensitive data
                assert "password" not in all_calls.lower()

    def test_calculate_position_profit_logs_ticket_not_account(self) -> None:
        """calculate_position_profit() should log ticket, not account info."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_deal = MagicMock()
        mock_deal.profit = 100.0
        mock_deal.commission = -2.0
        mock_deal.swap = -1.0

        with patch.object(mt5, "history_deals_get") as mock_deals_get:
            mock_deals_get.return_value = (mock_deal,)

            with patch("mt5linux.logger") as mock_logger:
                mt5.calculate_position_profit(12345)
                call_args = str(mock_logger.debug.call_args_list)
                # Ticket is OK to log
                assert "12345" in call_args
                # Account/login/password should not be logged
                assert "password" not in call_args.lower()
                assert "login" not in call_args.lower()


# =============================================================================
# Additional Tests: Edge Cases and Connection Error Handling
# =============================================================================


@pytest.mark.unit
class TestHistoryConnectionErrors:
    """Tests for connection error handling in history methods."""

    def test_get_position_history_connection_error_raises(self) -> None:
        """get_position_history() should raise HistoryRetrievalError on connection error."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_orders_get:
            mock_orders_get.side_effect = HistoryRetrievalError("Connection lost")

            with pytest.raises(HistoryRetrievalError) as exc_info:
                mt5.get_position_history(12345)

            assert "Connection" in str(exc_info.value) or "lost" in str(exc_info.value)

    def test_calculate_position_profit_connection_error_raises(self) -> None:
        """calculate_position_profit() should raise on connection error."""
        from mt5linux import HistoryRetrievalError, MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_deals_get") as mock_deals_get:
            mock_deals_get.side_effect = HistoryRetrievalError("Connection lost")

            with pytest.raises(HistoryRetrievalError):
                mt5.calculate_position_profit(12345)


@pytest.mark.unit
class TestHistoryEdgeCases:
    """Tests for edge cases in history retrieval."""

    def _create_mock_mt5(self, return_value):
        """Helper to create MT5 instance with mocked connection."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = return_value
        mt5._MetaTrader5__conn = mock_conn
        return mt5, mock_conn

    def test_history_orders_total_same_date_returns_zero(self) -> None:
        """history_orders_total() with same date should return zero gracefully."""
        mt5, _ = self._create_mock_mt5(0)

        same_date = datetime(2024, 1, 15)

        # Equal dates should be allowed and return 0
        result = mt5.history_orders_total(same_date, same_date)
        assert result == 0

    def test_get_orders_history_future_dates_returns_empty(self) -> None:
        """get_orders_history() with future dates should return empty tuple."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "history_orders_get") as mock_history_get:
            mock_history_get.return_value = ()

            future_from = datetime.now() + timedelta(days=30)
            future_to = datetime.now() + timedelta(days=60)

            result = mt5.get_orders_history(future_from, future_to)

            assert result == ()

    def test_history_deals_get_invalid_symbol_returns_empty(self) -> None:
        """history_deals_get() with non-existent symbol should return empty, not error."""
        mt5, _ = self._create_mock_mt5(())  # MT5 returns empty for invalid symbol

        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 31)

        # Should not raise, just return empty
        result = mt5.history_deals_get(date_from, date_to, group="*NONEXISTENT*")
        assert result == ()
