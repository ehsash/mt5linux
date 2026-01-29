"""Unit tests for order execution functionality.

This module tests:
- Trading exception classes (Task 1)
- Order request validation (Task 2)
- Audit logging for trading operations (Task 3)
- order_send method extensions (Task 4)
- Order result interpretation (Task 5)
- Verification callback hook (Task 6)
- Failure detection hook (Task 7)
- Backward compatibility (Task 8)
"""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Exception class imports will fail initially (RED phase)
from mt5linux import MetaTrader5
from mt5linux.process_manager import MT5LinuxError


# =============================================================================
# Task 1: Trading Exception Classes Tests
# =============================================================================
@pytest.mark.unit
class TestTradingExceptions:
    """Test trading exception classes hierarchy and messages."""

    def test_trade_error_inherits_from_mt5linux_error(self) -> None:
        """TradeError should inherit from MT5LinuxError."""
        from mt5linux import TradeError

        assert issubclass(TradeError, MT5LinuxError)

    def test_trade_validation_error_inherits_from_trade_error(self) -> None:
        """TradeValidationError should inherit from TradeError."""
        from mt5linux import TradeError, TradeValidationError

        assert issubclass(TradeValidationError, TradeError)

    def test_order_execution_error_inherits_from_trade_error(self) -> None:
        """OrderExecutionError should inherit from TradeError."""
        from mt5linux import OrderExecutionError, TradeError

        assert issubclass(OrderExecutionError, TradeError)

    def test_order_timeout_error_inherits_from_trade_error(self) -> None:
        """OrderTimeoutError should inherit from TradeError."""
        from mt5linux import OrderTimeoutError, TradeError

        assert issubclass(OrderTimeoutError, TradeError)

    def test_trade_validation_error_contains_actionable_message(self) -> None:
        """TradeValidationError should contain actionable recovery suggestion."""
        from mt5linux import TradeValidationError

        error = TradeValidationError("Missing required field 'symbol'")
        assert "symbol" in str(error)

    def test_order_execution_error_contains_retcode(self) -> None:
        """OrderExecutionError should accept and store retcode context."""
        from mt5linux import OrderExecutionError

        error = OrderExecutionError("Order rejected", retcode=10006)
        assert "rejected" in str(error).lower() or error.retcode == 10006

    def test_order_timeout_error_message(self) -> None:
        """OrderTimeoutError should have clear timeout message."""
        from mt5linux import OrderTimeoutError

        error = OrderTimeoutError("Order submission timed out after 30s")
        assert "timed out" in str(error).lower()

    def test_exception_can_preserve_cause(self) -> None:
        """Trading exceptions should preserve original cause via 'from'."""
        from mt5linux import TradeValidationError

        original = ValueError("invalid value")
        try:
            try:
                raise original
            except ValueError as e:
                raise TradeValidationError("Validation failed") from e
        except TradeValidationError as e:
            assert e.__cause__ is original


# =============================================================================
# Task 2: Order Request Validation Tests
# =============================================================================
@pytest.mark.unit
class TestOrderValidation:
    """Test order request validation logic."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with mocked connection."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            # Set required attributes
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True
            return mt5

    def test_validate_missing_action_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Missing action field should raise TradeValidationError."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {"symbol": "EURUSD", "volume": 0.1, "type": 0}

        with pytest.raises(TradeValidationError, match="action"):
            mt5_instance._validate_order_request(request)

    def test_validate_invalid_action_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Invalid action value should raise TradeValidationError."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {
            "action": 999,  # Invalid action
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
        }

        with pytest.raises(TradeValidationError, match="action"):
            mt5_instance._validate_order_request(request)

    def test_validate_deal_missing_symbol_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_DEAL without symbol should raise error."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "volume": 0.1,
            "type": 0,
        }

        with pytest.raises(TradeValidationError, match="symbol"):
            mt5_instance._validate_order_request(request)

    def test_validate_deal_missing_volume_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_DEAL without volume should raise error."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "type": 0,
        }

        with pytest.raises(TradeValidationError, match="volume"):
            mt5_instance._validate_order_request(request)

    def test_validate_negative_volume_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Negative volume should raise TradeValidationError."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": -0.1,  # Negative
            "type": 0,
        }

        with pytest.raises(TradeValidationError, match="volume"):
            mt5_instance._validate_order_request(request)

    def test_validate_zero_volume_raises_error(self, mt5_instance: MetaTrader5) -> None:
        """Zero volume should raise TradeValidationError."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0,  # Zero
            "type": 0,
        }

        with pytest.raises(TradeValidationError, match="volume"):
            mt5_instance._validate_order_request(request)

    def test_validate_deal_missing_type_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_DEAL without type should raise error."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
        }

        with pytest.raises(TradeValidationError, match="type"):
            mt5_instance._validate_order_request(request)

    def test_validate_valid_deal_request_passes(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Valid TRADE_ACTION_DEAL request should pass validation."""
        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        result = mt5_instance._validate_order_request(request)
        assert result == request

    def test_validate_sltp_action_passes_without_symbol(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_SLTP should not require symbol (modifies position)."""
        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_SLTP,
            "position": 12345,
            "sl": 1.0500,
            "tp": 1.0700,
        }

        result = mt5_instance._validate_order_request(request)
        assert result == request

    def test_validate_modify_action_passes_without_symbol(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_MODIFY should not require symbol."""
        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_MODIFY,
            "order": 12345,
            "price": 1.0600,
        }

        result = mt5_instance._validate_order_request(request)
        assert result == request

    def test_validate_remove_action_passes_without_symbol(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_REMOVE should not require symbol."""
        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_REMOVE,
            "order": 12345,
        }

        result = mt5_instance._validate_order_request(request)
        assert result == request

    def test_validate_wrong_type_action_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Non-integer action should raise TradeValidationError."""
        from mt5linux import TradeValidationError

        request: Dict[str, Any] = {
            "action": "DEAL",  # String instead of int
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
        }

        with pytest.raises(TradeValidationError, match="action"):
            mt5_instance._validate_order_request(request)

    def test_validate_pending_order_requires_symbol_volume_type(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_PENDING should require symbol, volume, type like DEAL."""
        from mt5linux import TradeValidationError

        # Missing symbol
        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_PENDING,
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY_LIMIT,
        }

        with pytest.raises(TradeValidationError, match="symbol"):
            mt5_instance._validate_order_request(request)

    def test_validate_valid_pending_order_passes(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Valid TRADE_ACTION_PENDING request should pass validation."""
        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_PENDING,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY_LIMIT,
            "price": 1.0500,
        }

        result = mt5_instance._validate_order_request(request)
        assert result == request

    def test_validate_close_by_action_passes_without_symbol(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """TRADE_ACTION_CLOSE_BY should not require symbol/volume/type."""
        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_CLOSE_BY,
            "position": 12345,
            "position_by": 12346,
        }

        result = mt5_instance._validate_order_request(request)
        assert result == request

    def test_validate_none_request_raises_error(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """None request should raise TradeValidationError."""
        from mt5linux import TradeValidationError

        with pytest.raises(TradeValidationError, match="Invalid request"):
            mt5_instance._validate_order_request(None)  # type: ignore

    def test_validate_empty_dict_raises_error(self, mt5_instance: MetaTrader5) -> None:
        """Empty dict request should raise TradeValidationError for missing action."""
        from mt5linux import TradeValidationError

        with pytest.raises(TradeValidationError, match="action"):
            mt5_instance._validate_order_request({})


# =============================================================================
# Task 3: Audit Logging Tests
# =============================================================================
@pytest.mark.unit
class TestAuditLogging:
    """Test audit logging for trading operations."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with mocked connection."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True
            return mt5

    def test_log_order_submission_logs_symbol(
        self, mt5_instance: MetaTrader5, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Audit log should include symbol."""
        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
        }

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_order_submission(request, "submitted")
            # Verify logger was called
            assert mock_logger.info.called
            call_args = str(mock_logger.info.call_args)
            assert "EURUSD" in call_args

    def test_log_order_submission_logs_action(self, mt5_instance: MetaTrader5) -> None:
        """Audit log should include action type."""
        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
        }

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_order_submission(request, "submitted")
            call_args = str(mock_logger.info.call_args)
            assert "action" in call_args.lower()

    def test_log_order_submission_logs_volume(self, mt5_instance: MetaTrader5) -> None:
        """Audit log should include volume."""
        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
        }

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_order_submission(request, "submitted")
            call_args = str(mock_logger.info.call_args)
            assert "0.1" in call_args

    def test_log_order_submission_does_not_log_price(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Audit log must NOT include price (sensitive data)."""
        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
            "price": 1.12345,
        }

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_order_submission(request, "submitted")
            call_args = str(mock_logger.info.call_args)
            # Price value should not appear
            assert "1.12345" not in call_args

    def test_log_order_submission_does_not_log_sl(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Audit log must NOT include stop loss (sensitive data)."""
        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
            "sl": 1.11000,
        }

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_order_submission(request, "submitted")
            call_args = str(mock_logger.info.call_args)
            assert "1.11" not in call_args

    def test_log_order_submission_does_not_log_tp(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Audit log must NOT include take profit (sensitive data)."""
        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
            "tp": 1.15000,
        }

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_order_submission(request, "submitted")
            call_args = str(mock_logger.info.call_args)
            assert "1.15" not in call_args

    def test_log_order_submission_logs_retcode_when_provided(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Audit log should include retcode when provided."""
        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
        }

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_order_submission(request, "completed", retcode=10009)
            call_args = str(mock_logger.info.call_args)
            assert "10009" in call_args


# =============================================================================
# Task 4: order_send Extension Tests
# =============================================================================
@pytest.mark.unit
class TestOrderSend:
    """Test order_send method extensions."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with mocked connection."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True
            mt5._lock = MagicMock()

            # Mock connection
            mock_conn = MagicMock()
            mt5._MetaTrader5__conn = mock_conn

            return mt5

    def test_order_send_validates_request_before_sending(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """order_send should validate request before rpyc call."""
        from mt5linux import TradeValidationError

        invalid_request: Dict[str, Any] = {"symbol": "EURUSD"}  # Missing action

        with pytest.raises(TradeValidationError):
            mt5_instance.order_send(invalid_request)

    def test_order_send_logs_before_submission(self, mt5_instance: MetaTrader5) -> None:
        """order_send should call audit log before submission."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(mt5_instance, "_log_order_submission") as mock_log:
            with patch.object(
                mt5_instance, "_validate_order_request", return_value=request
            ):
                with patch.object(mt5_instance, "_on_order_submitted"):
                    mt5_instance.order_send(request)

            # Should log "submitted" before sending
            calls = [str(c) for c in mock_log.call_args_list]
            assert any("submitted" in c for c in calls)

    def test_order_send_logs_after_completion(self, mt5_instance: MetaTrader5) -> None:
        """order_send should call audit log after completion."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(mt5_instance, "_log_order_submission") as mock_log:
            with patch.object(
                mt5_instance, "_validate_order_request", return_value=request
            ):
                with patch.object(mt5_instance, "_on_order_submitted"):
                    mt5_instance.order_send(request)

            # Should log "completed" after result
            calls = [str(c) for c in mock_log.call_args_list]
            assert any("completed" in c for c in calls)

    def test_order_send_returns_original_result_format(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """order_send should return original OrderSendResult format."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.order = 12345
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(
            mt5_instance, "_validate_order_request", return_value=request
        ):
            with patch.object(mt5_instance, "_log_order_submission"):
                with patch.object(mt5_instance, "_on_order_submitted"):
                    result = mt5_instance.order_send(request)

        assert result.retcode == 10009
        assert result.order == 12345

    def test_order_send_calls_on_order_submitted_on_success(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """order_send should call _on_order_submitted on success."""
        mock_result = MagicMock()
        mock_result.retcode = 10009  # TRADE_RETCODE_DONE
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(
            mt5_instance, "_validate_order_request", return_value=request
        ):
            with patch.object(mt5_instance, "_log_order_submission"):
                with patch.object(mt5_instance, "_on_order_submitted") as mock_callback:
                    mt5_instance.order_send(request)

        mock_callback.assert_called_once()

    def test_order_send_calls_on_order_failed_on_failure(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """order_send should call _on_order_failed on failure."""
        mock_result = MagicMock()
        mock_result.retcode = 10006  # TRADE_RETCODE_REJECT
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(
            mt5_instance, "_validate_order_request", return_value=request
        ):
            with patch.object(mt5_instance, "_log_order_submission"):
                with patch.object(mt5_instance, "_on_order_failed") as mock_callback:
                    mt5_instance.order_send(request)

        mock_callback.assert_called_once()


# =============================================================================
# Task 5: Order Result Interpretation Tests
# =============================================================================
@pytest.mark.unit
class TestRetcodeInterpretation:
    """Test order result/retcode interpretation."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            return mt5

    def test_interpret_done_retcode(self, mt5_instance: MetaTrader5) -> None:
        """TRADE_RETCODE_DONE should return success message."""
        message = mt5_instance._interpret_retcode(10009)
        assert "success" in message.lower() or "done" in message.lower()

    def test_interpret_placed_retcode(self, mt5_instance: MetaTrader5) -> None:
        """TRADE_RETCODE_PLACED should return placed message."""
        message = mt5_instance._interpret_retcode(10008)
        assert "placed" in message.lower()

    def test_interpret_reject_retcode(self, mt5_instance: MetaTrader5) -> None:
        """TRADE_RETCODE_REJECT should return rejection message."""
        message = mt5_instance._interpret_retcode(10006)
        assert "reject" in message.lower()

    def test_interpret_invalid_retcode(self, mt5_instance: MetaTrader5) -> None:
        """TRADE_RETCODE_INVALID should return invalid message."""
        message = mt5_instance._interpret_retcode(10013)
        assert "invalid" in message.lower()

    def test_interpret_no_money_retcode(self, mt5_instance: MetaTrader5) -> None:
        """TRADE_RETCODE_NO_MONEY should return insufficient funds message."""
        message = mt5_instance._interpret_retcode(10019)
        assert "money" in message.lower() or "fund" in message.lower()

    def test_interpret_market_closed_retcode(self, mt5_instance: MetaTrader5) -> None:
        """TRADE_RETCODE_MARKET_CLOSED should return market closed message."""
        message = mt5_instance._interpret_retcode(10018)
        assert "market" in message.lower() and "closed" in message.lower()

    def test_interpret_unknown_retcode(self, mt5_instance: MetaTrader5) -> None:
        """Unknown retcode should return generic message with code."""
        message = mt5_instance._interpret_retcode(99999)
        assert "99999" in message or "unknown" in message.lower()


# =============================================================================
# Task 6 & 7: Callback Hooks Tests
# =============================================================================
@pytest.mark.unit
class TestCallbackHooks:
    """Test verification and failure callback hooks."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            return mt5

    def test_on_order_submitted_method_exists(self, mt5_instance: MetaTrader5) -> None:
        """_on_order_submitted method should exist."""
        assert hasattr(mt5_instance, "_on_order_submitted")
        assert callable(mt5_instance._on_order_submitted)

    def test_on_order_submitted_accepts_result(self, mt5_instance: MetaTrader5) -> None:
        """_on_order_submitted should accept order result."""
        from mt5linux import OrderVerificationResult

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.retcode = 10009
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        # Mock verification (Story 3.2 integration)
        success_verification = OrderVerificationResult(
            verified=True, order_ticket=12345
        )

        with patch.object(
            mt5_instance, "_verify_with_retry", return_value=success_verification
        ):
            with patch.object(mt5_instance, "_log_verification_result"):
                # Should not raise
                mt5_instance._on_order_submitted(mock_result)

    def test_on_order_failed_method_exists(self, mt5_instance: MetaTrader5) -> None:
        """_on_order_failed method should exist."""
        assert hasattr(mt5_instance, "_on_order_failed")
        assert callable(mt5_instance._on_order_failed)

    def test_on_order_failed_accepts_result_and_request(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_failed should accept result and original request."""
        mock_result = MagicMock()
        mock_result.retcode = 10006

        request: Dict[str, Any] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": 0,
        }

        # Should not raise
        mt5_instance._on_order_failed(mock_result, request)


# =============================================================================
# Task 8: Backward Compatibility Tests
# =============================================================================
@pytest.mark.unit
class TestBackwardCompatibility:
    """Test backward compatibility of order_send."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with mocked connection."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True
            mt5._lock = MagicMock()

            mock_conn = MagicMock()
            mt5._MetaTrader5__conn = mock_conn

            return mt5

    def test_order_send_accepts_dict_request(self, mt5_instance: MetaTrader5) -> None:
        """order_send should accept dict request (original API)."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
            "price": 1.12345,
            "sl": 1.11000,
            "tp": 1.15000,
            "deviation": 20,
            "magic": 234000,
            "comment": "test order",
        }

        with patch.object(
            mt5_instance, "_validate_order_request", return_value=request
        ):
            with patch.object(mt5_instance, "_log_order_submission"):
                with patch.object(mt5_instance, "_on_order_submitted"):
                    result = mt5_instance.order_send(request)

        assert result is not None

    def test_order_send_signature_unchanged(self) -> None:
        """order_send should have the same signature (single request parameter)."""
        import inspect

        sig = inspect.signature(MetaTrader5.order_send)
        params = list(sig.parameters.keys())

        # Should be: self, request
        assert "self" in params
        assert "request" in params
        assert len(params) == 2

    def test_order_send_passes_request_to_rpyc(self, mt5_instance: MetaTrader5) -> None:
        """order_send should pass request to rpyc connection."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(
            mt5_instance, "_validate_order_request", return_value=request
        ):
            with patch.object(mt5_instance, "_log_order_submission"):
                with patch.object(mt5_instance, "_on_order_submitted"):
                    mt5_instance.order_send(request)

        # Verify rpyc was called
        mt5_instance._MetaTrader5__conn.eval.assert_called_once()
        call_arg = mt5_instance._MetaTrader5__conn.eval.call_args[0][0]
        assert "order_send" in call_arg


# =============================================================================
# Thread Safety and Latency Tests (Code Review Additions)
# =============================================================================
@pytest.mark.unit
class TestThreadSafetyAndLatency:
    """Test thread safety and latency tracking features."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with real threading lock."""
        import threading

        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True
            mt5._lock = threading.Lock()  # Real lock for thread safety tests

            mock_conn = MagicMock()
            mt5._MetaTrader5__conn = mock_conn

            return mt5

    def test_order_send_acquires_lock(self, mt5_instance: MetaTrader5) -> None:
        """order_send should acquire thread lock during execution."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        # Replace lock with a mock to verify it's used
        mock_lock = MagicMock()
        mt5_instance._lock = mock_lock

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(mt5_instance, "_log_order_submission"):
            with patch.object(mt5_instance, "_on_order_submitted"):
                mt5_instance.order_send(request)

        # Verify lock context manager was used
        mock_lock.__enter__.assert_called()
        mock_lock.__exit__.assert_called()

    def test_order_send_stores_elapsed_time(self, mt5_instance: MetaTrader5) -> None:
        """order_send should store elapsed time for latency monitoring."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch.object(mt5_instance, "_log_order_submission"):
            with patch.object(mt5_instance, "_on_order_submitted"):
                mt5_instance.order_send(request)

        # Verify elapsed time is stored
        assert hasattr(mt5_instance, "_last_order_elapsed_ms")
        assert isinstance(mt5_instance._last_order_elapsed_ms, float)
        assert mt5_instance._last_order_elapsed_ms >= 0


# =============================================================================
# Integration Tests (Less Mocking)
# =============================================================================
@pytest.mark.unit
class TestOrderSendIntegration:
    """Integration tests with minimal mocking."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance for integration testing."""
        import threading

        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True
            mt5._lock = threading.Lock()

            mock_conn = MagicMock()
            mt5._MetaTrader5__conn = mock_conn

            return mt5

    def test_full_order_send_flow_success(self, mt5_instance: MetaTrader5) -> None:
        """Test complete order_send flow without mocking internal methods."""
        mock_result = MagicMock()
        mock_result.retcode = 10009  # Success
        mock_result.order = 12345
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        # Only mock the logger to avoid file I/O
        with patch("mt5linux.logger"):
            result = mt5_instance.order_send(request)

        # Verify the result
        assert result.retcode == 10009
        assert result.order == 12345

    def test_full_order_send_flow_failure(self, mt5_instance: MetaTrader5) -> None:
        """Test complete order_send flow for failure case."""
        mock_result = MagicMock()
        mock_result.retcode = 10006  # Rejected
        mt5_instance._MetaTrader5__conn.eval.return_value = mock_result

        request: Dict[str, Any] = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": MetaTrader5.ORDER_TYPE_BUY,
        }

        with patch("mt5linux.logger"):
            result = mt5_instance.order_send(request)

        assert result.retcode == 10006

    def test_validation_to_rpyc_integration(self, mt5_instance: MetaTrader5) -> None:
        """Test that validation runs before rpyc call."""
        from mt5linux import TradeValidationError

        # Invalid request (missing action)
        request: Dict[str, Any] = {"symbol": "EURUSD"}

        # rpyc should never be called for invalid requests
        with pytest.raises(TradeValidationError):
            mt5_instance.order_send(request)

        # Verify rpyc was NOT called
        mt5_instance._MetaTrader5__conn.eval.assert_not_called()
