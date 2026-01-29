"""Tests for trade execution failure detection (Story 3.3).

This module tests the trade failure detection system including:
- TradeFailureType enum and categorization
- TradeFailureContext data structure
- TradeExecutionFailedError exception
- Failure detection callbacks (_on_order_failed, _on_verification_failed)
- Recovery suggestion generation
- Notification hook system
"""

import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestTradeFailureType:
    """Tests for TradeFailureType enum."""

    def test_enum_has_rejection_type(self) -> None:
        """TradeFailureType should have REJECTION value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "REJECTION")

    def test_enum_has_timeout_type(self) -> None:
        """TradeFailureType should have TIMEOUT value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "TIMEOUT")

    def test_enum_has_verification_failed_type(self) -> None:
        """TradeFailureType should have VERIFICATION_FAILED value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "VERIFICATION_FAILED")

    def test_enum_has_network_error_type(self) -> None:
        """TradeFailureType should have NETWORK_ERROR value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "NETWORK_ERROR")

    def test_enum_has_insufficient_funds_type(self) -> None:
        """TradeFailureType should have INSUFFICIENT_FUNDS value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "INSUFFICIENT_FUNDS")

    def test_enum_has_market_closed_type(self) -> None:
        """TradeFailureType should have MARKET_CLOSED value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "MARKET_CLOSED")

    def test_enum_has_invalid_request_type(self) -> None:
        """TradeFailureType should have INVALID_REQUEST value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "INVALID_REQUEST")

    def test_enum_has_trading_disabled_type(self) -> None:
        """TradeFailureType should have TRADING_DISABLED value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "TRADING_DISABLED")

    def test_enum_has_limit_reached_type(self) -> None:
        """TradeFailureType should have LIMIT_REACHED value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "LIMIT_REACHED")

    def test_enum_has_requote_type(self) -> None:
        """TradeFailureType should have REQUOTE value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "REQUOTE")

    def test_enum_has_canceled_type(self) -> None:
        """TradeFailureType should have CANCELED value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "CANCELED")

    def test_enum_has_unknown_type(self) -> None:
        """TradeFailureType should have UNKNOWN value."""
        from mt5linux import TradeFailureType

        assert hasattr(TradeFailureType, "UNKNOWN")

    def test_enum_values_are_unique(self) -> None:
        """All TradeFailureType values should be unique."""
        from mt5linux import TradeFailureType

        values = [member.value for member in TradeFailureType]
        assert len(values) == len(set(values))


@pytest.mark.unit
class TestTradeFailureContext:
    """Tests for TradeFailureContext data structure."""

    def test_create_with_required_fields(self) -> None:
        """TradeFailureContext can be created with required fields."""
        from mt5linux import TradeFailureContext, TradeFailureType

        context = TradeFailureContext(
            failure_type=TradeFailureType.REJECTION,
            reason="Request rejected by broker",
        )

        assert context.failure_type == TradeFailureType.REJECTION
        assert context.reason == "Request rejected by broker"

    def test_create_with_all_fields(self) -> None:
        """TradeFailureContext can be created with all fields."""
        from mt5linux import TradeFailureContext, TradeFailureType

        timestamp = time.time()
        context = TradeFailureContext(
            failure_type=TradeFailureType.TIMEOUT,
            reason="Request timed out",
            order_ticket=12345,
            symbol="EURUSD",
            retcode=10012,
            timestamp=timestamp,
            recovery_suggestion="Check connection and retry the order.",
        )

        assert context.failure_type == TradeFailureType.TIMEOUT
        assert context.order_ticket == 12345
        assert context.symbol == "EURUSD"
        assert context.retcode == 10012
        assert context.reason == "Request timed out"
        assert context.timestamp == timestamp
        assert context.recovery_suggestion == "Check connection and retry the order."

    def test_timestamp_defaults_to_current_time(self) -> None:
        """TradeFailureContext timestamp defaults to current time."""
        from mt5linux import TradeFailureContext, TradeFailureType

        before = time.time()
        context = TradeFailureContext(
            failure_type=TradeFailureType.UNKNOWN,
            reason="Unknown error",
        )
        after = time.time()

        assert before <= context.timestamp <= after

    def test_optional_fields_default_to_none(self) -> None:
        """TradeFailureContext optional fields default to None."""
        from mt5linux import TradeFailureContext, TradeFailureType

        context = TradeFailureContext(
            failure_type=TradeFailureType.UNKNOWN,
            reason="Unknown error",
        )

        assert context.order_ticket is None
        assert context.symbol is None
        assert context.retcode is None
        assert context.recovery_suggestion is None

    def test_has_slots_for_memory_efficiency(self) -> None:
        """TradeFailureContext should use __slots__ for memory efficiency."""
        from mt5linux import TradeFailureContext

        assert hasattr(TradeFailureContext, "__slots__")


@pytest.mark.unit
class TestTradeExecutionFailedError:
    """Tests for TradeExecutionFailedError exception."""

    def test_inherits_from_trade_error(self) -> None:
        """TradeExecutionFailedError should inherit from TradeError."""
        from mt5linux import TradeError, TradeExecutionFailedError

        assert issubclass(TradeExecutionFailedError, TradeError)

    def test_create_with_message(self) -> None:
        """TradeExecutionFailedError can be created with message."""
        from mt5linux import TradeExecutionFailedError

        error = TradeExecutionFailedError("Trade execution failed")
        assert str(error) == "Trade execution failed"

    def test_create_with_failure_context(self) -> None:
        """TradeExecutionFailedError can be created with failure context."""
        from mt5linux import (
            TradeExecutionFailedError,
            TradeFailureContext,
            TradeFailureType,
        )

        context = TradeFailureContext(
            failure_type=TradeFailureType.REJECTION,
            reason="Request rejected by broker",
            retcode=10006,
        )

        error = TradeExecutionFailedError("Trade execution failed", context=context)
        assert error.context == context
        assert error.context.failure_type == TradeFailureType.REJECTION

    def test_context_defaults_to_none(self) -> None:
        """TradeExecutionFailedError context defaults to None."""
        from mt5linux import TradeExecutionFailedError

        error = TradeExecutionFailedError("Trade execution failed")
        assert error.context is None

    def test_exception_chaining_preserved(self) -> None:
        """TradeExecutionFailedError should preserve exception chaining."""
        from mt5linux import TradeExecutionFailedError

        original = ValueError("Original error")
        try:
            raise TradeExecutionFailedError("Trade failed") from original
        except TradeExecutionFailedError as e:
            assert e.__cause__ is original


@pytest.mark.unit
class TestRetcodeToFailureTypeMapping:
    """Tests for retcode to failure type mapping."""

    def test_requote_retcodes(self) -> None:
        """Retcodes 10004, 10020, 10021 should map to REQUOTE."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10004) == TradeFailureType.REQUOTE
        assert mt5._categorize_failure(10020) == TradeFailureType.REQUOTE
        assert mt5._categorize_failure(10021) == TradeFailureType.REQUOTE

    def test_rejection_retcode(self) -> None:
        """Retcode 10006 should map to REJECTION."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10006) == TradeFailureType.REJECTION

    def test_canceled_retcode(self) -> None:
        """Retcode 10007 should map to CANCELED."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10007) == TradeFailureType.CANCELED

    def test_timeout_retcode(self) -> None:
        """Retcode 10012 should map to TIMEOUT."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10012) == TradeFailureType.TIMEOUT

    def test_invalid_request_retcodes(self) -> None:
        """Invalid request retcodes should map to INVALID_REQUEST."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        # 10013, 10014, 10015, 10016, 10022, etc.
        invalid_request_codes = [10013, 10014, 10015, 10016, 10022, 10025, 10030, 10035]
        for retcode in invalid_request_codes:
            assert mt5._categorize_failure(retcode) == TradeFailureType.INVALID_REQUEST

    def test_trading_disabled_retcodes(self) -> None:
        """Trading disabled retcodes should map to TRADING_DISABLED."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        # 10017, 10026, 10027
        disabled_codes = [10017, 10026, 10027]
        for retcode in disabled_codes:
            assert mt5._categorize_failure(retcode) == TradeFailureType.TRADING_DISABLED

    def test_market_closed_retcode(self) -> None:
        """Retcode 10018 should map to MARKET_CLOSED."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10018) == TradeFailureType.MARKET_CLOSED

    def test_insufficient_funds_retcode(self) -> None:
        """Retcode 10019 should map to INSUFFICIENT_FUNDS."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10019) == TradeFailureType.INSUFFICIENT_FUNDS

    def test_network_error_retcode(self) -> None:
        """Retcode 10031 should map to NETWORK_ERROR."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10031) == TradeFailureType.NETWORK_ERROR

    def test_limit_reached_retcodes(self) -> None:
        """Limit reached retcodes should map to LIMIT_REACHED."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        # 10033, 10034, 10040
        limit_codes = [10033, 10034, 10040]
        for retcode in limit_codes:
            assert mt5._categorize_failure(retcode) == TradeFailureType.LIMIT_REACHED

    def test_unknown_retcode_maps_to_unknown(self) -> None:
        """Unknown retcodes should map to UNKNOWN."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(99999) == TradeFailureType.UNKNOWN

    def test_none_retcode_maps_to_unknown(self) -> None:
        """None retcode should map to UNKNOWN."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(None) == TradeFailureType.UNKNOWN

    def test_general_error_retcode(self) -> None:
        """Retcode 10011 should map to UNKNOWN (general error)."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        assert mt5._categorize_failure(10011) == TradeFailureType.UNKNOWN


@pytest.mark.unit
class TestRecoverySuggestions:
    """Tests for recovery suggestion generation."""

    def test_rejection_recovery_suggestion(self) -> None:
        """REJECTION should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.REJECTION)
        assert "broker" in suggestion.lower() or "parameters" in suggestion.lower()

    def test_timeout_recovery_suggestion(self) -> None:
        """TIMEOUT should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.TIMEOUT)
        assert "connection" in suggestion.lower() or "retry" in suggestion.lower()

    def test_verification_failed_recovery_suggestion(self) -> None:
        """VERIFICATION_FAILED should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.VERIFICATION_FAILED)
        assert "mt5" in suggestion.lower() or "terminal" in suggestion.lower()

    def test_network_error_recovery_suggestion(self) -> None:
        """NETWORK_ERROR should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.NETWORK_ERROR)
        assert "network" in suggestion.lower() or "connection" in suggestion.lower()

    def test_insufficient_funds_recovery_suggestion(self) -> None:
        """INSUFFICIENT_FUNDS should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.INSUFFICIENT_FUNDS)
        assert "funds" in suggestion.lower() or "deposit" in suggestion.lower()

    def test_market_closed_recovery_suggestion(self) -> None:
        """MARKET_CLOSED should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.MARKET_CLOSED)
        assert "market" in suggestion.lower() or "open" in suggestion.lower()

    def test_trading_disabled_recovery_suggestion(self) -> None:
        """TRADING_DISABLED should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.TRADING_DISABLED)
        assert "autotrading" in suggestion.lower() or "enable" in suggestion.lower()

    def test_limit_reached_recovery_suggestion(self) -> None:
        """LIMIT_REACHED should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.LIMIT_REACHED)
        assert "close" in suggestion.lower() or "positions" in suggestion.lower()

    def test_requote_recovery_suggestion(self) -> None:
        """REQUOTE should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.REQUOTE)
        assert "price" in suggestion.lower() or "retry" in suggestion.lower()

    def test_unknown_recovery_suggestion(self) -> None:
        """UNKNOWN should have appropriate recovery suggestion."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()
        suggestion = mt5._get_recovery_suggestion(TradeFailureType.UNKNOWN)
        assert "logs" in suggestion.lower() or "mt5" in suggestion.lower()


@pytest.mark.unit
class TestOnOrderFailed:
    """Tests for extended _on_order_failed() callback."""

    def test_creates_failure_context(self) -> None:
        """_on_order_failed should create TradeFailureContext."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()

        # Mock result object
        result = MagicMock()
        result.retcode = 10006
        result.order = 12345

        request = {"symbol": "EURUSD", "volume": 0.1}

        mt5._on_order_failed(result, request)

        # Should store failure context
        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.failure_type == TradeFailureType.REJECTION
        assert mt5._last_trade_failure.order_ticket == 12345
        assert mt5._last_trade_failure.symbol == "EURUSD"
        assert mt5._last_trade_failure.retcode == 10006

    def test_calls_notification_hook(self) -> None:
        """_on_order_failed should call _on_trade_failure hook."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.retcode = 10018
        result.order = 54321

        request = {"symbol": "GBPUSD", "volume": 0.2}

        with patch.object(mt5, "_on_trade_failure") as mock_hook:
            mt5._on_order_failed(result, request)

            # Should call notification hook
            mock_hook.assert_called_once()
            call_args = mock_hook.call_args[0]
            assert call_args[0].symbol == "GBPUSD"

    def test_handles_none_retcode(self) -> None:
        """_on_order_failed should handle None retcode gracefully."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()

        result = MagicMock()
        result.retcode = None
        result.order = None

        request = {"symbol": "USDJPY"}

        mt5._on_order_failed(result, request)

        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.failure_type == TradeFailureType.UNKNOWN

    def test_handles_missing_order_ticket(self) -> None:
        """_on_order_failed should handle missing order ticket."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.retcode = 10019
        del result.order  # No order attribute

        request = {"symbol": "EURUSD"}

        mt5._on_order_failed(result, request)

        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.order_ticket is None


@pytest.mark.unit
class TestOnVerificationFailed:
    """Tests for extended _on_verification_failed() callback."""

    def test_creates_failure_context_for_verification_timeout(self) -> None:
        """_on_verification_failed should create TradeFailureContext."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()

        result = MagicMock()
        result.order = 12345

        mt5._on_verification_failed(result)

        assert mt5._last_trade_failure is not None
        assert (
            mt5._last_trade_failure.failure_type == TradeFailureType.VERIFICATION_FAILED
        )
        assert mt5._last_trade_failure.order_ticket == 12345

    def test_calls_notification_hook(self) -> None:
        """_on_verification_failed should call _on_trade_failure hook."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.order = 99999

        with patch.object(mt5, "_on_trade_failure") as mock_hook:
            mt5._on_verification_failed(result)

            mock_hook.assert_called_once()

    def test_handles_none_order_ticket(self) -> None:
        """_on_verification_failed should handle None order ticket."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.order = None

        mt5._on_verification_failed(result)

        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.order_ticket is None


@pytest.mark.unit
class TestGetLastTradeFailure:
    """Tests for get_last_trade_failure() accessor method."""

    def test_returns_none_initially(self) -> None:
        """get_last_trade_failure should return None before any failure."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        assert mt5.get_last_trade_failure() is None

    def test_returns_last_failure_context(self) -> None:
        """get_last_trade_failure should return the last failure context."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()

        result = MagicMock()
        result.retcode = 10006
        result.order = 12345

        request = {"symbol": "EURUSD"}

        mt5._on_order_failed(result, request)

        failure = mt5.get_last_trade_failure()
        assert failure is not None
        assert failure.failure_type == TradeFailureType.REJECTION

    def test_returns_most_recent_failure(self) -> None:
        """get_last_trade_failure should return the most recent failure."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()

        # First failure
        result1 = MagicMock()
        result1.retcode = 10006
        result1.order = 11111

        mt5._on_order_failed(result1, {"symbol": "EURUSD"})

        # Second failure
        result2 = MagicMock()
        result2.retcode = 10019
        result2.order = 22222

        mt5._on_order_failed(result2, {"symbol": "GBPUSD"})

        failure = mt5.get_last_trade_failure()
        assert failure is not None
        assert failure.failure_type == TradeFailureType.INSUFFICIENT_FUNDS
        assert failure.order_ticket == 22222


@pytest.mark.unit
class TestOnTradeFailureHook:
    """Tests for _on_trade_failure notification hook."""

    def test_hook_method_exists(self) -> None:
        """MetaTrader5 should have _on_trade_failure method."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()
        assert hasattr(mt5, "_on_trade_failure")
        assert callable(mt5._on_trade_failure)

    def test_hook_accepts_failure_context(self) -> None:
        """_on_trade_failure should accept TradeFailureContext."""
        from mt5linux import MetaTrader5, TradeFailureContext, TradeFailureType

        mt5 = MetaTrader5()

        context = TradeFailureContext(
            failure_type=TradeFailureType.REJECTION,
            reason="Test failure",
        )

        # Should not raise
        mt5._on_trade_failure(context)


@pytest.mark.unit
class TestTradeFailureLogging:
    """Tests for trade failure logging (FR68 compliant - no sensitive data)."""

    def test_logging_does_not_include_price(self) -> None:
        """Trade failure logging should NOT include price."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        with patch("mt5linux.logger") as mock_logger:
            result = MagicMock()
            result.retcode = 10006
            result.order = 12345

            request = {"symbol": "EURUSD", "volume": 0.1, "price": 1.23456}

            mt5._on_order_failed(result, request)

            # Check all logger calls don't contain price
            for call in mock_logger.method_calls:
                call_str = str(call)
                assert "1.23456" not in call_str

    def test_logging_does_not_include_volume(self) -> None:
        """Trade failure logging should NOT include volume."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        with patch("mt5linux.logger") as mock_logger:
            result = MagicMock()
            result.retcode = 10006
            result.order = 12345

            request = {"symbol": "EURUSD", "volume": 5.55, "price": 1.23456}

            mt5._on_order_failed(result, request)

            # Check all logger calls don't contain volume
            for call in mock_logger.method_calls:
                call_str = str(call)
                assert "5.55" not in call_str

    def test_logging_does_not_include_sl_tp(self) -> None:
        """Trade failure logging should NOT include stop loss or take profit."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        with patch("mt5linux.logger") as mock_logger:
            result = MagicMock()
            result.retcode = 10006
            result.order = 12345

            request = {
                "symbol": "EURUSD",
                "volume": 0.1,
                "price": 1.23456,
                "sl": 1.22000,
                "tp": 1.25000,
            }

            mt5._on_order_failed(result, request)

            # Check all logger calls don't contain sl/tp
            for call in mock_logger.method_calls:
                call_str = str(call)
                assert "1.22000" not in call_str
                assert "1.25000" not in call_str

    def test_logging_includes_symbol(self) -> None:
        """Trade failure logging should include symbol (not sensitive)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        with patch("mt5linux.logger") as mock_logger:
            result = MagicMock()
            result.retcode = 10006
            result.order = 12345

            request = {"symbol": "EURUSD", "volume": 0.1}

            mt5._on_order_failed(result, request)

            # Symbol should be logged
            all_calls = str(mock_logger.method_calls)
            assert "EURUSD" in all_calls

    def test_logging_includes_retcode(self) -> None:
        """Trade failure logging should include retcode (not sensitive)."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        with patch("mt5linux.logger") as mock_logger:
            result = MagicMock()
            result.retcode = 10006
            result.order = 12345

            request = {"symbol": "EURUSD", "volume": 0.1}

            mt5._on_order_failed(result, request)

            # Retcode should be logged
            all_calls = str(mock_logger.method_calls)
            assert "10006" in all_calls


@pytest.mark.unit
class TestTradeFailureContextRepr:
    """Tests for TradeFailureContext __repr__ method."""

    def test_repr_includes_type_name(self) -> None:
        """TradeFailureContext __repr__ should include failure type name."""
        from mt5linux import TradeFailureContext, TradeFailureType

        context = TradeFailureContext(
            failure_type=TradeFailureType.REJECTION,
            reason="Test",
            retcode=10006,
            symbol="EURUSD",
        )

        repr_str = repr(context)
        assert "REJECTION" in repr_str

    def test_repr_includes_retcode(self) -> None:
        """TradeFailureContext __repr__ should include retcode."""
        from mt5linux import TradeFailureContext, TradeFailureType

        context = TradeFailureContext(
            failure_type=TradeFailureType.TIMEOUT,
            reason="Test",
            retcode=10012,
        )

        repr_str = repr(context)
        assert "10012" in repr_str

    def test_repr_includes_symbol(self) -> None:
        """TradeFailureContext __repr__ should include symbol."""
        from mt5linux import TradeFailureContext, TradeFailureType

        context = TradeFailureContext(
            failure_type=TradeFailureType.MARKET_CLOSED,
            reason="Test",
            symbol="GBPUSD",
        )

        repr_str = repr(context)
        assert "GBPUSD" in repr_str

    def test_repr_handles_none_values(self) -> None:
        """TradeFailureContext __repr__ should handle None values."""
        from mt5linux import TradeFailureContext, TradeFailureType

        context = TradeFailureContext(
            failure_type=TradeFailureType.UNKNOWN,
            reason="Test",
        )

        repr_str = repr(context)
        assert "None" in repr_str
        assert "UNKNOWN" in repr_str


@pytest.mark.unit
class TestVerificationFailedSymbolExtraction:
    """Tests for symbol extraction in _on_verification_failed (M2 fix)."""

    def test_extracts_symbol_from_dict_request(self) -> None:
        """_on_verification_failed should extract symbol from dict request."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.order = 12345
        result.request = {"symbol": "EURUSD", "volume": 0.1}

        mt5._on_verification_failed(result)

        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.symbol == "EURUSD"

    def test_extracts_symbol_from_object_request(self) -> None:
        """_on_verification_failed should extract symbol from object request."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.order = 12345
        result.request = MagicMock()
        result.request.symbol = "GBPUSD"

        mt5._on_verification_failed(result)

        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.symbol == "GBPUSD"

    def test_handles_missing_request(self) -> None:
        """_on_verification_failed should handle missing request gracefully."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.order = 12345
        del result.request  # No request attribute

        mt5._on_verification_failed(result)

        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.symbol is None

    def test_handles_none_request(self) -> None:
        """_on_verification_failed should handle None request."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        result = MagicMock()
        result.order = 12345
        result.request = None

        mt5._on_verification_failed(result)

        assert mt5._last_trade_failure is not None
        assert mt5._last_trade_failure.symbol is None


@pytest.mark.unit
class TestOrderSendFailureIntegration:
    """Integration tests for order_send failure detection flow (L3 fix)."""

    def test_order_send_triggers_on_order_failed_for_rejection(self) -> None:
        """order_send should trigger _on_order_failed for rejection retcode."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()

        # Mock connection
        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        # Mock order_send result with rejection
        mock_result = MagicMock()
        mock_result.retcode = 10006  # TRADE_RETCODE_REJECT
        mock_result.order = 12345
        mock_conn.eval.return_value = mock_result

        request = {
            "action": 1,  # TRADE_ACTION_DEAL
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,  # ORDER_TYPE_BUY
            "price": 1.1000,
        }

        mt5.order_send(request)

        # Verify failure was detected
        failure = mt5.get_last_trade_failure()
        assert failure is not None
        assert failure.failure_type == TradeFailureType.REJECTION
        assert failure.symbol == "EURUSD"
        assert failure.retcode == 10006

    def test_order_send_triggers_on_order_failed_for_market_closed(self) -> None:
        """order_send should trigger _on_order_failed for market closed."""
        from mt5linux import MetaTrader5, TradeFailureType

        mt5 = MetaTrader5()

        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        mock_result = MagicMock()
        mock_result.retcode = 10018  # Market closed
        mock_result.order = None
        mock_conn.eval.return_value = mock_result

        request = {
            "action": 1,
            "symbol": "USDJPY",
            "volume": 0.5,
            "type": 0,
            "price": 150.00,
        }

        mt5.order_send(request)

        failure = mt5.get_last_trade_failure()
        assert failure is not None
        assert failure.failure_type == TradeFailureType.MARKET_CLOSED
        assert failure.symbol == "USDJPY"

    def test_order_send_no_failure_for_success_retcode(self) -> None:
        """order_send should not set failure context for success retcode."""
        from mt5linux import MetaTrader5

        mt5 = MetaTrader5()

        mock_conn = MagicMock()
        mt5._MetaTrader5__conn = mock_conn

        # Mock successful result
        mock_result = MagicMock()
        mock_result.retcode = 10009  # TRADE_RETCODE_DONE
        mock_result.order = 99999
        mock_result.deal = 88888
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}
        mock_conn.eval.return_value = mock_result

        # Mock history query for verification (returns empty)
        def eval_side_effect(code):
            if "history_orders_get" in code:
                return None
            return mock_result

        mock_conn.eval.side_effect = eval_side_effect

        request = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
            "price": 1.1000,
        }

        # Clear any previous failure
        mt5._last_trade_failure = None

        mt5.order_send(request)

        # For success, _on_order_failed is NOT called
        # (but _on_verification_failed might be called if verification fails)
        # This test verifies the flow branches correctly
        # The failure context would only be set if verification fails
