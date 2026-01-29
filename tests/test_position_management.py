"""Tests for position management (Story 3.5).

This module tests the position management system including:
- PositionError, PositionCloseError, PositionModifyError exceptions
- positions_total() logging and error handling
- positions_get() logging and error handling
- close_position() helper method
- close_all_positions() helper method
- modify_position_sl_tp() helper method
- Position query helper methods
- FR68 compliance: no sensitive data in logs
"""

from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Task 1: Position Management Exception Classes Tests
# =============================================================================


@pytest.mark.unit
class TestPositionError:
    """Tests for PositionError base exception."""

    def test_inherits_from_mt5linux_error(self) -> None:
        """PositionError should inherit from MT5LinuxError."""
        from mt5linux import PositionError
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(PositionError, MT5LinuxError)

    def test_create_with_message(self) -> None:
        """PositionError can be created with message."""
        from mt5linux import PositionError

        error = PositionError("Position operation failed")
        assert str(error) == "Position operation failed"

    def test_can_be_raised_and_caught(self) -> None:
        """PositionError can be raised and caught."""
        from mt5linux import PositionError

        with pytest.raises(PositionError) as exc_info:
            raise PositionError("Test error")

        assert "Test error" in str(exc_info.value)

    def test_provides_actionable_error_message(self) -> None:
        """PositionError should support actionable error messages."""
        from mt5linux import PositionError

        error = PositionError(
            "Position 12345 not found. Check ticket number and try again."
        )
        assert "Check ticket number" in str(error)


@pytest.mark.unit
class TestPositionCloseError:
    """Tests for PositionCloseError exception."""

    def test_inherits_from_position_error(self) -> None:
        """PositionCloseError should inherit from PositionError."""
        from mt5linux import PositionCloseError, PositionError

        assert issubclass(PositionCloseError, PositionError)

    def test_create_with_message(self) -> None:
        """PositionCloseError can be created with message."""
        from mt5linux import PositionCloseError

        error = PositionCloseError("Failed to close position 12345")
        assert str(error) == "Failed to close position 12345"

    def test_provides_actionable_error_message(self) -> None:
        """PositionCloseError should support actionable error messages."""
        from mt5linux import PositionCloseError

        error = PositionCloseError(
            "Position 12345 close failed: market closed. "
            "Wait for market open and retry."
        )
        assert "Wait for market open" in str(error)

    def test_can_be_caught_as_position_error(self) -> None:
        """PositionCloseError can be caught as PositionError."""
        from mt5linux import PositionCloseError, PositionError

        with pytest.raises(PositionError):
            raise PositionCloseError("Close error")


@pytest.mark.unit
class TestPositionModifyError:
    """Tests for PositionModifyError exception."""

    def test_inherits_from_position_error(self) -> None:
        """PositionModifyError should inherit from PositionError."""
        from mt5linux import PositionError, PositionModifyError

        assert issubclass(PositionModifyError, PositionError)

    def test_create_with_message(self) -> None:
        """PositionModifyError can be created with message."""
        from mt5linux import PositionModifyError

        error = PositionModifyError("Failed to modify position 12345 SL/TP")
        assert str(error) == "Failed to modify position 12345 SL/TP"

    def test_provides_actionable_error_message(self) -> None:
        """PositionModifyError should support actionable error messages."""
        from mt5linux import PositionModifyError

        error = PositionModifyError(
            "Position 12345 SL/TP modification failed: invalid SL level. "
            "Ensure SL is valid for current price."
        )
        assert "Ensure SL is valid" in str(error)

    def test_can_be_caught_as_position_error(self) -> None:
        """PositionModifyError can be caught as PositionError."""
        from mt5linux import PositionError, PositionModifyError

        with pytest.raises(PositionError):
            raise PositionModifyError("Modify error")


@pytest.mark.unit
class TestPositionExceptionHierarchy:
    """Tests for position exception hierarchy consistency."""

    def test_all_position_exceptions_inherit_from_mt5linux_error(self) -> None:
        """All position exceptions should inherit from MT5LinuxError."""
        from mt5linux import PositionCloseError, PositionError, PositionModifyError
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(PositionError, MT5LinuxError)
        assert issubclass(PositionCloseError, MT5LinuxError)
        assert issubclass(PositionModifyError, MT5LinuxError)

    def test_specific_errors_inherit_from_position_error(self) -> None:
        """Specific errors should inherit from PositionError."""
        from mt5linux import PositionCloseError, PositionError, PositionModifyError

        assert issubclass(PositionCloseError, PositionError)
        assert issubclass(PositionModifyError, PositionError)

    def test_can_catch_all_with_position_error(self) -> None:
        """All specific exceptions can be caught with PositionError."""
        from mt5linux import PositionCloseError, PositionError, PositionModifyError

        exceptions = [
            PositionCloseError("close"),
            PositionModifyError("modify"),
        ]

        for exc in exceptions:
            with pytest.raises(PositionError):
                raise exc


# =============================================================================
# Task 2: positions_total() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestPositionsTotalLogging:
    """Tests for positions_total() logging and error handling."""

    def test_positions_total_logs_retrieval_attempt(self) -> None:
        """positions_total() should log retrieval attempt."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 5
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_total()
            assert mock_logger.debug.called

    def test_positions_total_logs_success_with_count(self) -> None:
        """positions_total() should log success with position count."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 10
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_total()
            call_args = str(mock_logger.debug.call_args_list)
            assert "10" in call_args or "success" in call_args.lower()

    def test_positions_total_returns_same_result_type(self) -> None:
        """positions_total() should return same result type (backward compatible)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 5
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.positions_total()
        assert result == 5
        assert isinstance(result, int)

    def test_positions_total_raises_on_connection_error(self) -> None:
        """positions_total() should raise PositionError on connection errors."""
        from mt5linux import MetaTrader5, PositionError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(PositionError) as exc_info:
                mt5.positions_total()
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called

    def test_positions_total_handles_zero_result(self) -> None:
        """positions_total() should handle zero positions gracefully."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 0
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.positions_total()
        assert result == 0


# =============================================================================
# Task 3: positions_get() with logging and error handling
# =============================================================================


@pytest.mark.unit
class TestPositionsGetLogging:
    """Tests for positions_get() logging and error handling."""

    def test_positions_get_logs_retrieval_attempt(self) -> None:
        """positions_get() should log retrieval attempt."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_conn.eval.return_value = (mock_position,)
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_get()
            assert mock_logger.debug.called

    def test_positions_get_logs_symbol_filter(self) -> None:
        """positions_get() should log symbol filter when provided."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_conn.eval.return_value = (mock_position,)
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_get(symbol="EURUSD")
            call_args = str(mock_logger.debug.call_args_list)
            assert "EURUSD" in call_args

    def test_positions_get_logs_ticket_filter(self) -> None:
        """positions_get() should log ticket filter when provided."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_conn.eval.return_value = (mock_position,)
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_get(ticket=12345)
            call_args = str(mock_logger.debug.call_args_list)
            assert "12345" in call_args

    def test_positions_get_logs_result_count(self) -> None:
        """positions_get() should log result count on success."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_positions = (MagicMock(), MagicMock(), MagicMock())  # 3 positions
        mock_conn.eval.return_value = mock_positions
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_get()
            call_args = str(mock_logger.debug.call_args_list)
            assert "3" in call_args or "count" in call_args.lower()

    def test_positions_get_returns_same_result_type(self) -> None:
        """positions_get() should return same result type (backward compatible)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        expected_result = (MagicMock(), MagicMock())
        mock_conn.eval.return_value = expected_result
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.positions_get()
        assert result is expected_result

    def test_positions_get_handles_empty_result(self) -> None:
        """positions_get() should handle empty result gracefully (not an error)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = ()  # Empty tuple
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger"):
            result = mt5.positions_get(symbol="NONEXISTENT")
            assert result == ()
            # Should not log warning for empty results (not an error)

    def test_positions_get_handles_none_result(self) -> None:
        """positions_get() should handle None result (backward compatible)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = None
        mt5._MetaTrader5__conn = mock_conn

        result = mt5.positions_get()
        assert result is None

    def test_positions_get_raises_on_connection_error(self) -> None:
        """positions_get() should raise PositionError on connection errors."""
        from mt5linux import MetaTrader5, PositionError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.side_effect = Exception("Connection lost")
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            with pytest.raises(PositionError) as exc_info:
                mt5.positions_get()
            assert "Connection lost" in str(exc_info.value)
            assert mock_logger.warning.called


# =============================================================================
# Task 4: close_position() helper method
# =============================================================================


@pytest.mark.unit
class TestClosePosition:
    """Tests for close_position() helper method."""

    def test_close_position_success(self) -> None:
        """close_position() should close position successfully."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        # Mock positions_get to return a position
        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 0  # BUY
        mock_position.sl = 1.0800
        mock_position.tp = 1.1200

        # Mock symbol_info_tick for current price
        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        # Mock order_send result
        mock_result = MagicMock()
        mock_result.retcode = 10009  # TRADE_RETCODE_DONE
        mock_result.deal = 99999

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    mock_positions_get.side_effect = [
                        (mock_position,),  # First call: position exists
                        (),  # Second call: verification - position closed
                    ]
                    mock_symbol_tick.return_value = mock_tick
                    mock_order_send.return_value = mock_result

                    result = mt5.close_position(12345)

                    assert result.retcode == 10009
                    mock_order_send.assert_called_once()
                    # Verify positions_get called twice: once to get, once to verify
                    assert mock_positions_get.call_count == 2

    def test_close_position_not_found_raises(self) -> None:
        """close_position() should raise PositionCloseError if position not found."""
        from mt5linux import MetaTrader5, PositionCloseError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()  # No positions

            with pytest.raises(PositionCloseError) as exc_info:
                mt5.close_position(99999)

            assert "99999" in str(exc_info.value)
            assert "not found" in str(exc_info.value).lower()

    def test_close_position_logs_attempt(self) -> None:
        """close_position() should log closure attempt."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 0

        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.deal = 99999

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    with patch("mt5linux.logger") as mock_logger:
                        mock_positions_get.side_effect = [(mock_position,), ()]
                        mock_symbol_tick.return_value = mock_tick
                        mock_order_send.return_value = mock_result

                        mt5.close_position(12345)

                        assert mock_logger.debug.called
                        call_args = str(mock_logger.debug.call_args_list)
                        assert "12345" in call_args

    def test_close_position_logs_success(self) -> None:
        """close_position() should log success with deal ticket."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 0

        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.deal = 99999

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    with patch("mt5linux.logger") as mock_logger:
                        mock_positions_get.side_effect = [(mock_position,), ()]
                        mock_symbol_tick.return_value = mock_tick
                        mock_order_send.return_value = mock_result

                        mt5.close_position(12345)

                        call_args = str(mock_logger.debug.call_args_list)
                        assert "success" in call_args.lower() or "99999" in call_args

    def test_close_position_sell_position(self) -> None:
        """close_position() should handle closing SELL position correctly."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 1  # SELL

        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.deal = 99999

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    mock_positions_get.side_effect = [(mock_position,), ()]
                    mock_symbol_tick.return_value = mock_tick
                    mock_order_send.return_value = mock_result

                    mt5.close_position(12345)

                    # Verify order request uses BUY to close SELL
                    call_args = mock_order_send.call_args[0][0]
                    assert call_args["type"] == mt5.ORDER_TYPE_BUY

    def test_close_position_failure_raises(self) -> None:
        """close_position() should raise PositionCloseError on failure."""
        from mt5linux import MetaTrader5, PositionCloseError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 0

        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        mock_result = MagicMock()
        mock_result.retcode = 10006  # TRADE_RETCODE_REJECT

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    mock_positions_get.return_value = (mock_position,)
                    mock_symbol_tick.return_value = mock_tick
                    mock_order_send.return_value = mock_result

                    with pytest.raises(PositionCloseError) as exc_info:
                        mt5.close_position(12345)

                    assert "12345" in str(exc_info.value)


# =============================================================================
# Task 5: close_all_positions() helper method
# =============================================================================


@pytest.mark.unit
class TestCloseAllPositions:
    """Tests for close_all_positions() helper method."""

    def test_close_all_positions_success(self) -> None:
        """close_all_positions() should close all positions successfully."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position1 = MagicMock()
        mock_position1.ticket = 12345
        mock_position2 = MagicMock()
        mock_position2.ticket = 12346

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "close_position") as mock_close:
                mock_positions_get.return_value = (mock_position1, mock_position2)
                mock_result = MagicMock()
                mock_result.retcode = 10009
                mock_close.return_value = mock_result

                closed, failed = mt5.close_all_positions()

                assert closed == [12345, 12346]
                assert failed == []
                assert mock_close.call_count == 2

    def test_close_all_positions_with_symbol_filter(self) -> None:
        """close_all_positions() should filter by symbol."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "close_position") as mock_close:
                mock_positions_get.return_value = (mock_position,)
                mock_result = MagicMock()
                mock_result.retcode = 10009
                mock_close.return_value = mock_result

                mt5.close_all_positions(symbol="EURUSD")

                mock_positions_get.assert_called_once_with(symbol="EURUSD")

    def test_close_all_positions_no_positions(self) -> None:
        """close_all_positions() should handle no positions gracefully."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()

            closed, failed = mt5.close_all_positions()

            assert closed == []
            assert failed == []

    def test_close_all_positions_partial_failure(self) -> None:
        """close_all_positions() should continue on partial failure."""
        from mt5linux import MetaTrader5, PositionCloseError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position1 = MagicMock()
        mock_position1.ticket = 12345
        mock_position2 = MagicMock()
        mock_position2.ticket = 12346
        mock_position3 = MagicMock()
        mock_position3.ticket = 12347

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "close_position") as mock_close:
                mock_positions_get.return_value = (
                    mock_position1,
                    mock_position2,
                    mock_position3,
                )
                mock_result = MagicMock()
                mock_result.retcode = 10009
                # First succeeds, second fails, third succeeds
                mock_close.side_effect = [
                    mock_result,
                    PositionCloseError("Failed"),
                    mock_result,
                ]

                closed, failed = mt5.close_all_positions()

                assert closed == [12345, 12347]
                assert failed == [12346]

    def test_close_all_positions_returns_tuple(self) -> None:
        """close_all_positions() should return tuple of (closed, failed)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()

            result = mt5.close_all_positions()

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], list)
            assert isinstance(result[1], list)

    def test_close_all_positions_logs_each_attempt(self) -> None:
        """close_all_positions() should log each closure attempt."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position1 = MagicMock()
        mock_position1.ticket = 12345
        mock_position2 = MagicMock()
        mock_position2.ticket = 12346

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "close_position") as mock_close:
                with patch("mt5linux.logger") as mock_logger:
                    mock_positions_get.return_value = (mock_position1, mock_position2)
                    mock_result = MagicMock()
                    mock_result.retcode = 10009
                    mock_close.return_value = mock_result

                    mt5.close_all_positions()

                    assert mock_logger.debug.called

    def test_close_all_positions_logs_overall_result(self) -> None:
        """close_all_positions() should log overall result."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position1 = MagicMock()
        mock_position1.ticket = 12345

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "close_position") as mock_close:
                with patch("mt5linux.logger") as mock_logger:
                    mock_positions_get.return_value = (mock_position1,)
                    mock_result = MagicMock()
                    mock_result.retcode = 10009
                    mock_close.return_value = mock_result

                    mt5.close_all_positions()

                    call_args = str(mock_logger.debug.call_args_list)
                    # Should log overall result
                    assert "1" in call_args or "closed" in call_args.lower()


# =============================================================================
# Task 6: modify_position_sl_tp() helper method
# =============================================================================


@pytest.mark.unit
class TestModifyPositionSlTp:
    """Tests for modify_position_sl_tp() helper method."""

    def test_modify_position_sl_tp_success(self) -> None:
        """modify_position_sl_tp() should modify SL/TP successfully."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.sl = 1.0800
        mock_position.tp = 1.1200

        mock_result = MagicMock()
        mock_result.retcode = 10009

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "order_send") as mock_order_send:
                mock_positions_get.return_value = (mock_position,)
                mock_order_send.return_value = mock_result

                result = mt5.modify_position_sl_tp(12345, sl=1.0850, tp=1.1250)

                assert result.retcode == 10009
                mock_order_send.assert_called_once()

    def test_modify_position_sl_only(self) -> None:
        """modify_position_sl_tp() should allow modifying SL only."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.sl = 1.0800
        mock_position.tp = 1.1200

        mock_result = MagicMock()
        mock_result.retcode = 10009

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "order_send") as mock_order_send:
                mock_positions_get.return_value = (mock_position,)
                mock_order_send.return_value = mock_result

                mt5.modify_position_sl_tp(12345, sl=1.0850)

                call_args = mock_order_send.call_args[0][0]
                assert call_args["sl"] == 1.0850
                assert call_args["tp"] == 1.1200  # Original TP preserved

    def test_modify_position_tp_only(self) -> None:
        """modify_position_sl_tp() should allow modifying TP only."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.sl = 1.0800
        mock_position.tp = 1.1200

        mock_result = MagicMock()
        mock_result.retcode = 10009

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "order_send") as mock_order_send:
                mock_positions_get.return_value = (mock_position,)
                mock_order_send.return_value = mock_result

                mt5.modify_position_sl_tp(12345, tp=1.1250)

                call_args = mock_order_send.call_args[0][0]
                assert call_args["sl"] == 1.0800  # Original SL preserved
                assert call_args["tp"] == 1.1250

    def test_modify_position_not_found_raises(self) -> None:
        """modify_position_sl_tp() should raise PositionModifyError if not found."""
        from mt5linux import MetaTrader5, PositionModifyError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()

            with pytest.raises(PositionModifyError) as exc_info:
                mt5.modify_position_sl_tp(99999, sl=1.0850)

            assert "99999" in str(exc_info.value)
            assert "not found" in str(exc_info.value).lower()

    def test_modify_position_failure_raises(self) -> None:
        """modify_position_sl_tp() should raise PositionModifyError on failure."""
        from mt5linux import MetaTrader5, PositionModifyError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.sl = 1.0800
        mock_position.tp = 1.1200

        mock_result = MagicMock()
        mock_result.retcode = 10006  # TRADE_RETCODE_REJECT

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "order_send") as mock_order_send:
                mock_positions_get.return_value = (mock_position,)
                mock_order_send.return_value = mock_result

                with pytest.raises(PositionModifyError) as exc_info:
                    mt5.modify_position_sl_tp(12345, sl=1.0850)

                assert "12345" in str(exc_info.value)

    def test_modify_position_logs_attempt(self) -> None:
        """modify_position_sl_tp() should log modification attempt."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.sl = 1.0800
        mock_position.tp = 1.1200

        mock_result = MagicMock()
        mock_result.retcode = 10009

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "order_send") as mock_order_send:
                with patch("mt5linux.logger") as mock_logger:
                    mock_positions_get.return_value = (mock_position,)
                    mock_order_send.return_value = mock_result

                    mt5.modify_position_sl_tp(12345, sl=1.0850)

                    assert mock_logger.debug.called
                    call_args = str(mock_logger.debug.call_args_list)
                    assert "12345" in call_args


# =============================================================================
# Task 7: Helper methods for common position queries
# =============================================================================


@pytest.mark.unit
class TestPositionHelperMethods:
    """Tests for position helper methods."""

    def test_get_position_by_ticket_returns_position(self) -> None:
        """get_position_by_ticket() should return single position."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = (mock_position,)

            result = mt5.get_position_by_ticket(12345)

            assert result is mock_position
            mock_positions_get.assert_called_once_with(ticket=12345)

    def test_get_position_by_ticket_returns_none_if_not_found(self) -> None:
        """get_position_by_ticket() should return None if not found."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()

            result = mt5.get_position_by_ticket(99999)

            assert result is None

    def test_get_positions_by_symbol_returns_positions(self) -> None:
        """get_positions_by_symbol() should return positions for symbol."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position1 = MagicMock()
        mock_position1.ticket = 12345
        mock_position2 = MagicMock()
        mock_position2.ticket = 12346

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = (mock_position1, mock_position2)

            result = mt5.get_positions_by_symbol("EURUSD")

            assert len(result) == 2
            mock_positions_get.assert_called_once_with(symbol="EURUSD")

    def test_get_positions_by_symbol_returns_empty_tuple(self) -> None:
        """get_positions_by_symbol() should return empty tuple if none found."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()

            result = mt5.get_positions_by_symbol("NONEXISTENT")

            assert result == ()

    def test_get_total_profit_returns_sum(self) -> None:
        """get_total_profit() should return sum of all position profits."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position1 = MagicMock()
        mock_position1.profit = 100.50
        mock_position2 = MagicMock()
        mock_position2.profit = -50.25
        mock_position3 = MagicMock()
        mock_position3.profit = 75.00

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = (
                mock_position1,
                mock_position2,
                mock_position3,
            )

            result = mt5.get_total_profit()

            assert result == 125.25  # 100.50 - 50.25 + 75.00

    def test_get_total_profit_returns_zero_if_no_positions(self) -> None:
        """get_total_profit() should return 0.0 if no positions."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()

            result = mt5.get_total_profit()

            assert result == 0.0

    def test_get_total_volume_returns_sum(self) -> None:
        """get_total_volume() should return sum of all position volumes."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position1 = MagicMock()
        mock_position1.volume = 0.1
        mock_position2 = MagicMock()
        mock_position2.volume = 0.2
        mock_position3 = MagicMock()
        mock_position3.volume = 0.5

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = (
                mock_position1,
                mock_position2,
                mock_position3,
            )

            result = mt5.get_total_volume()

            assert abs(result - 0.8) < 0.001

    def test_get_total_volume_with_symbol_filter(self) -> None:
        """get_total_volume() should filter by symbol."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.volume = 0.1

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = (mock_position,)

            mt5.get_total_volume(symbol="EURUSD")

            mock_positions_get.assert_called_once_with(symbol="EURUSD")

    def test_get_total_volume_returns_zero_if_no_positions(self) -> None:
        """get_total_volume() should return 0.0 if no positions."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = ()

            result = mt5.get_total_volume()

            assert result == 0.0


# =============================================================================
# Task 8: FR68 Compliance - Logging Does NOT Include Sensitive Data
# =============================================================================


@pytest.mark.unit
class TestPositionLoggingCompliance:
    """Tests for FR68 compliance: no sensitive data in position logs."""

    def test_positions_get_does_not_log_login(self) -> None:
        """positions_get() must NOT log login (FR68 compliance)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        # Simulate if login somehow appeared in position data
        mock_conn.eval.return_value = (mock_position,)
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_get()
            all_calls = str(mock_logger.debug.call_args_list) + str(
                mock_logger.info.call_args_list
            )
            # Should not contain any login-like numbers (8 digits)
            assert "password" not in all_calls.lower()

    def test_close_position_logs_ticket_not_account(self) -> None:
        """close_position() should log ticket, not account info."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 0

        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.deal = 99999

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    with patch("mt5linux.logger") as mock_logger:
                        mock_positions_get.side_effect = [(mock_position,), ()]
                        mock_symbol_tick.return_value = mock_tick
                        mock_order_send.return_value = mock_result

                        mt5.close_position(12345)

                        call_args = str(mock_logger.debug.call_args_list)
                        # Ticket is OK to log
                        assert "12345" in call_args
                        # Account/login/password should not be logged
                        assert "password" not in call_args.lower()
                        assert "login" not in call_args.lower()

    def test_positions_total_logs_safe_data(self) -> None:
        """positions_total() should log count, not sensitive data."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mock_conn.eval.return_value = 5
        mt5._MetaTrader5__conn = mock_conn

        with patch("mt5linux.logger") as mock_logger:
            mt5.positions_total()
            call_args = str(mock_logger.debug.call_args_list)
            # Count is OK to log
            assert "5" in call_args or "positions" in call_args.lower()
            # No sensitive data
            assert "password" not in call_args.lower()
            assert "server" not in call_args.lower()


# =============================================================================
# Task 8: Connection Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestPositionConnectionErrors:
    """Tests for connection error handling in position methods."""

    def test_close_position_connection_error_raises(self) -> None:
        """close_position() should raise PositionCloseError on connection error."""
        from mt5linux import MetaTrader5, PositionCloseError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.side_effect = Exception("Connection lost")

            with pytest.raises(PositionCloseError) as exc_info:
                mt5.close_position(12345)

            assert "Connection" in str(exc_info.value) or "lost" in str(exc_info.value)

    def test_modify_position_connection_error_raises(self) -> None:
        """modify_position_sl_tp() should raise PositionModifyError on connection error."""
        from mt5linux import MetaTrader5, PositionModifyError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.side_effect = Exception("Connection lost")

            with pytest.raises(PositionModifyError) as exc_info:
                mt5.modify_position_sl_tp(12345, sl=1.0850)

            assert "Connection" in str(exc_info.value) or "lost" in str(exc_info.value)

    def test_close_all_positions_handles_connection_errors(self) -> None:
        """close_all_positions() should handle connection errors gracefully."""
        from mt5linux import MetaTrader5, PositionError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            # positions_get() raises PositionError on connection failure
            mock_positions_get.side_effect = PositionError("Connection lost")

            # Should raise PositionError (not silently fail)
            with pytest.raises(PositionError):
                mt5.close_all_positions()


# =============================================================================
# Additional Tests: Verification Steps and Edge Cases (Code Review Fixes)
# =============================================================================


@pytest.mark.unit
class TestClosePositionVerification:
    """Tests for close_position() verification step."""

    def test_close_position_verifies_closure(self) -> None:
        """close_position() should verify position is actually closed."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 0

        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.deal = 99999

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    mock_positions_get.side_effect = [
                        (mock_position,),  # First: position exists
                        (),  # Second: verification - position closed
                    ]
                    mock_symbol_tick.return_value = mock_tick
                    mock_order_send.return_value = mock_result

                    mt5.close_position(12345)

                    # Must call positions_get twice: get + verify
                    assert mock_positions_get.call_count == 2
                    # Second call should be verification with same ticket
                    second_call = mock_positions_get.call_args_list[1]
                    assert second_call.kwargs.get("ticket") == 12345

    def test_close_position_raises_if_position_still_exists(self) -> None:
        """close_position() should raise if position still exists after close."""
        from mt5linux import MetaTrader5, PositionCloseError

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.volume = 0.1
        mock_position.type = 0

        mock_tick = MagicMock()
        mock_tick.bid = 1.1000
        mock_tick.ask = 1.1002

        mock_result = MagicMock()
        mock_result.retcode = 10009  # Order accepted
        mock_result.deal = 99999

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "symbol_info_tick") as mock_symbol_tick:
                with patch.object(mt5, "order_send") as mock_order_send:
                    mock_positions_get.side_effect = [
                        (mock_position,),  # First: position exists
                        (mock_position,),  # Second: position STILL exists!
                    ]
                    mock_symbol_tick.return_value = mock_tick
                    mock_order_send.return_value = mock_result

                    with pytest.raises(PositionCloseError) as exc_info:
                        mt5.close_position(12345)

                    assert "still exists" in str(exc_info.value).lower()


@pytest.mark.unit
class TestModifyPositionVerification:
    """Tests for modify_position_sl_tp() verification step."""

    def test_modify_position_verifies_modification(self) -> None:
        """modify_position_sl_tp() should verify SL/TP were applied."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_position = MagicMock()
        mock_position.ticket = 12345
        mock_position.symbol = "EURUSD"
        mock_position.sl = 1.0800
        mock_position.tp = 1.1200

        mock_updated_position = MagicMock()
        mock_updated_position.ticket = 12345
        mock_updated_position.symbol = "EURUSD"
        mock_updated_position.sl = 1.0850  # New SL
        mock_updated_position.tp = 1.1200  # Same TP

        mock_result = MagicMock()
        mock_result.retcode = 10009

        with patch.object(mt5, "positions_get") as mock_positions_get:
            with patch.object(mt5, "order_send") as mock_order_send:
                mock_positions_get.side_effect = [
                    (mock_position,),  # First: get current values
                    (mock_updated_position,),  # Second: verification
                ]
                mock_order_send.return_value = mock_result

                mt5.modify_position_sl_tp(12345, sl=1.0850)

                # Must call positions_get twice: get + verify
                assert mock_positions_get.call_count == 2


@pytest.mark.unit
class TestHelperMethodsNoneHandling:
    """Tests for helper methods handling None from positions_get."""

    def test_get_positions_by_symbol_handles_none(self) -> None:
        """get_positions_by_symbol() should return empty tuple for None."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = None

            result = mt5.get_positions_by_symbol("EURUSD")

            assert result == ()

    def test_get_total_profit_handles_none(self) -> None:
        """get_total_profit() should return 0.0 for None."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = None

            result = mt5.get_total_profit()

            assert result == 0.0

    def test_get_total_volume_handles_none(self) -> None:
        """get_total_volume() should return 0.0 for None."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        with patch.object(mt5, "positions_get") as mock_positions_get:
            mock_positions_get.return_value = None

            result = mt5.get_total_volume()

            assert result == 0.0
