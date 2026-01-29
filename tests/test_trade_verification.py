"""Unit tests for trade execution verification functionality.

This module tests Story 3.2: Trade Execution Verification:
- Verification exception classes (Task 1)
- Order verification data structures (Task 2)
- Verification query method (Task 3)
- Retry logic with exponential backoff (Task 4)
- _on_order_submitted() integration (Task 5)
- Verification result logging (Task 6)
- Verification status accessor (Task 7)
- Failure detection hook (Task 8)
"""

from unittest.mock import MagicMock, patch

import pytest

from mt5linux import MetaTrader5
from mt5linux.process_manager import MT5LinuxError


# =============================================================================
# Task 1: Verification Exception Classes Tests
# =============================================================================
@pytest.mark.unit
class TestVerificationExceptions:
    """Test verification exception classes hierarchy and messages."""

    def test_verification_timeout_error_inherits_from_trade_error(self) -> None:
        """VerificationTimeoutError should inherit from TradeError."""
        from mt5linux import TradeError, VerificationTimeoutError

        assert issubclass(VerificationTimeoutError, TradeError)

    def test_verification_failed_error_inherits_from_trade_error(self) -> None:
        """VerificationFailedError should inherit from TradeError."""
        from mt5linux import TradeError, VerificationFailedError

        assert issubclass(VerificationFailedError, TradeError)

    def test_verification_timeout_error_message_contains_retry_info(self) -> None:
        """VerificationTimeoutError should contain actionable message with retry info."""
        from mt5linux import VerificationTimeoutError

        error = VerificationTimeoutError(
            "Order 12345 verification failed after 3 retries. "
            "Check MT5 terminal for order status."
        )
        assert "12345" in str(error)
        assert "retries" in str(error).lower()

    def test_verification_failed_error_message_contains_reason(self) -> None:
        """VerificationFailedError should contain actionable message with reason."""
        from mt5linux import VerificationFailedError

        error = VerificationFailedError(
            "Order 12345 cannot be confirmed: order not found in history. "
            "Verify order ticket and try again."
        )
        assert "12345" in str(error)
        assert "history" in str(error).lower()

    def test_verification_timeout_error_preserves_cause(self) -> None:
        """VerificationTimeoutError should preserve original cause via 'from'."""
        from mt5linux import VerificationTimeoutError

        original = TimeoutError("connection timeout")
        try:
            try:
                raise original
            except TimeoutError as e:
                raise VerificationTimeoutError("Verification timed out") from e
        except VerificationTimeoutError as e:
            assert e.__cause__ is original

    def test_verification_failed_error_preserves_cause(self) -> None:
        """VerificationFailedError should preserve original cause via 'from'."""
        from mt5linux import VerificationFailedError

        original = RuntimeError("MT5 query failed")
        try:
            try:
                raise original
            except RuntimeError as e:
                raise VerificationFailedError("Verification failed") from e
        except VerificationFailedError as e:
            assert e.__cause__ is original

    def test_verification_timeout_error_is_instance_of_mt5linux_error(self) -> None:
        """VerificationTimeoutError should also be MT5LinuxError."""
        from mt5linux import VerificationTimeoutError

        assert issubclass(VerificationTimeoutError, MT5LinuxError)

    def test_verification_failed_error_is_instance_of_mt5linux_error(self) -> None:
        """VerificationFailedError should also be MT5LinuxError."""
        from mt5linux import VerificationFailedError

        assert issubclass(VerificationFailedError, MT5LinuxError)


# =============================================================================
# Task 2: Order Verification Data Structures Tests
# =============================================================================
@pytest.mark.unit
class TestOrderVerificationResult:
    """Test OrderVerificationResult data structure."""

    def test_order_verification_result_exists(self) -> None:
        """OrderVerificationResult class should exist."""
        from mt5linux import OrderVerificationResult

        assert OrderVerificationResult is not None

    def test_order_verification_result_has_verified_field(self) -> None:
        """OrderVerificationResult should have verified bool field."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(verified=True, order_ticket=12345)
        assert hasattr(result, "verified")
        assert result.verified is True

    def test_order_verification_result_has_order_ticket_field(self) -> None:
        """OrderVerificationResult should have order_ticket field."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(verified=True, order_ticket=12345)
        assert hasattr(result, "order_ticket")
        assert result.order_ticket == 12345

    def test_order_verification_result_has_deal_ticket_field(self) -> None:
        """OrderVerificationResult should have deal_ticket field (optional)."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, deal_ticket=67890
        )
        assert hasattr(result, "deal_ticket")
        assert result.deal_ticket == 67890

    def test_order_verification_result_deal_ticket_defaults_none(self) -> None:
        """OrderVerificationResult deal_ticket should default to None."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(verified=True, order_ticket=12345)
        assert result.deal_ticket is None

    def test_order_verification_result_has_execution_time_field(self) -> None:
        """OrderVerificationResult should have execution_time field (optional)."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, execution_time=1582303777
        )
        assert hasattr(result, "execution_time")
        assert result.execution_time == 1582303777

    def test_order_verification_result_has_execution_price_field(self) -> None:
        """OrderVerificationResult should have execution_price field (optional)."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, execution_price=1.10264
        )
        assert hasattr(result, "execution_price")
        assert result.execution_price == 1.10264

    def test_order_verification_result_has_volume_field(self) -> None:
        """OrderVerificationResult should have volume field (optional)."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(verified=True, order_ticket=12345, volume=0.1)
        assert hasattr(result, "volume")
        assert result.volume == 0.1

    def test_order_verification_result_has_symbol_field(self) -> None:
        """OrderVerificationResult should have symbol field (optional)."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, symbol="EURUSD"
        )
        assert hasattr(result, "symbol")
        assert result.symbol == "EURUSD"

    def test_order_verification_result_has_verification_latency_ms(self) -> None:
        """OrderVerificationResult should have verification_latency_ms for Story 4.3."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, verification_latency_ms=45.5
        )
        assert hasattr(result, "verification_latency_ms")
        assert result.verification_latency_ms == 45.5

    def test_order_verification_result_has_attempts_count(self) -> None:
        """OrderVerificationResult should have attempts_count for retry tracking."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, attempts_count=2
        )
        assert hasattr(result, "attempts_count")
        assert result.attempts_count == 2

    def test_order_verification_result_has_reason_field(self) -> None:
        """OrderVerificationResult should have reason field for failure context."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=False, order_ticket=12345, reason="Order not found in history"
        )
        assert hasattr(result, "reason")
        assert result.reason == "Order not found in history"

    def test_order_verification_result_defaults(self) -> None:
        """OrderVerificationResult should have sensible defaults."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(verified=False, order_ticket=12345)
        assert result.deal_ticket is None
        assert result.execution_time is None
        assert result.execution_price is None
        assert result.volume is None
        assert result.symbol is None
        assert result.verification_latency_ms is None
        assert result.attempts_count is None
        assert result.reason is None


# =============================================================================
# Task 3: Verification Query Method Tests
# =============================================================================
@pytest.mark.unit
class TestQueryOrderExecution:
    """Test _query_order_execution method."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with mocked connection."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True

            mock_conn = MagicMock()
            mt5._MetaTrader5__conn = mock_conn

            return mt5

    def test_query_order_execution_method_exists(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution method should exist."""
        assert hasattr(mt5_instance, "_query_order_execution")
        assert callable(mt5_instance._query_order_execution)

    def test_query_order_execution_returns_verification_result(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return OrderVerificationResult."""
        from mt5linux import OrderVerificationResult

        # Mock successful order in history
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert isinstance(result, OrderVerificationResult)

    def test_query_order_execution_verified_true_on_filled_order(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return verified=True for FILLED order."""
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.verified is True

    def test_query_order_execution_verified_true_on_partial_order(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return verified=True for PARTIAL order."""
        mock_order = MagicMock()
        mock_order.state = 3  # ORDER_STATE_PARTIAL
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.verified is True

    def test_query_order_execution_verified_false_on_canceled(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return verified=False for CANCELED order."""
        mock_order = MagicMock()
        mock_order.state = 2  # ORDER_STATE_CANCELED
        mock_order.symbol = "EURUSD"

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.verified is False
        assert "state" in result.reason.lower() or "canceled" in result.reason.lower()

    def test_query_order_execution_verified_false_on_order_not_found(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return verified=False when order not found."""
        mt5_instance._MetaTrader5__conn.eval.return_value = None

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.verified is False
        assert "not found" in result.reason.lower()

    def test_query_order_execution_verified_false_on_empty_result(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return verified=False on empty result."""
        mt5_instance._MetaTrader5__conn.eval.return_value = ()

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.verified is False
        assert "not found" in result.reason.lower()

    def test_query_order_execution_verified_false_on_symbol_mismatch(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return verified=False on symbol mismatch."""
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "GBPUSD"  # Different symbol
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.25000

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.verified is False
        assert "symbol" in result.reason.lower() or "mismatch" in result.reason.lower()

    def test_query_order_execution_verified_false_on_volume_mismatch(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should return verified=False on volume mismatch."""
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.5  # Different volume than expected
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,  # Expected 0.1, got 0.5
        )

        assert result.verified is False
        assert "volume" in result.reason.lower() or "mismatch" in result.reason.lower()

    def test_query_order_execution_volume_tolerance(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should allow minor volume differences within tolerance."""
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1001  # Within 0.001 tolerance
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,  # Within tolerance of 0.1001
        )

        assert result.verified is True

    def test_query_order_execution_populates_execution_details(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should populate execution details on success."""
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.order_ticket == 12345
        assert result.deal_ticket == 67890
        assert result.execution_time == 1582303777
        assert result.execution_price == 1.10264
        assert result.volume == 0.1
        assert result.symbol == "EURUSD"

    def test_query_order_execution_measures_latency(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_query_order_execution should measure verification latency."""
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        result = mt5_instance._query_order_execution(
            order_ticket=12345,
            deal_ticket=67890,
            expected_symbol="EURUSD",
            expected_volume=0.1,
        )

        assert result.verification_latency_ms is not None
        assert isinstance(result.verification_latency_ms, float)
        assert result.verification_latency_ms >= 0


# =============================================================================
# Task 4: Retry Logic with Exponential Backoff Tests
# =============================================================================
@pytest.mark.unit
class TestVerifyWithRetry:
    """Test _verify_with_retry method with exponential backoff."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with mocked connection."""
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

    def test_verify_with_retry_method_exists(self, mt5_instance: MetaTrader5) -> None:
        """_verify_with_retry method should exist."""
        assert hasattr(mt5_instance, "_verify_with_retry")
        assert callable(mt5_instance._verify_with_retry)

    def test_verify_with_retry_returns_on_first_success(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_verify_with_retry should return immediately on first success."""
        from mt5linux import OrderVerificationResult

        # Mock _query_order_execution to return success
        success_result = OrderVerificationResult(
            verified=True, order_ticket=12345, attempts_count=1
        )

        with patch.object(
            mt5_instance, "_query_order_execution", return_value=success_result
        ) as mock_query:
            result = mt5_instance._verify_with_retry(
                order_ticket=12345,
                deal_ticket=67890,
                expected_symbol="EURUSD",
                expected_volume=0.1,
            )

        assert result.verified is True
        assert mock_query.call_count == 1

    def test_verify_with_retry_retries_on_failure(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_verify_with_retry should retry on verification failure."""
        from mt5linux import OrderVerificationResult

        # First two calls fail, third succeeds
        fail_result = OrderVerificationResult(
            verified=False, order_ticket=12345, reason="Not found"
        )
        success_result = OrderVerificationResult(
            verified=True, order_ticket=12345, attempts_count=3
        )

        with patch.object(
            mt5_instance,
            "_query_order_execution",
            side_effect=[fail_result, fail_result, success_result],
        ) as mock_query:
            with patch("time.sleep"):  # Don't actually sleep in tests
                result = mt5_instance._verify_with_retry(
                    order_ticket=12345,
                    deal_ticket=67890,
                    expected_symbol="EURUSD",
                    expected_volume=0.1,
                )

        assert result.verified is True
        assert mock_query.call_count == 3

    def test_verify_with_retry_raises_timeout_after_max_retries(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_verify_with_retry should raise VerificationTimeoutError after max retries."""
        from mt5linux import OrderVerificationResult, VerificationTimeoutError

        # All calls fail
        fail_result = OrderVerificationResult(
            verified=False, order_ticket=12345, reason="Not found"
        )

        with patch.object(
            mt5_instance, "_query_order_execution", return_value=fail_result
        ):
            with patch("time.sleep"):
                with pytest.raises(VerificationTimeoutError) as exc_info:
                    mt5_instance._verify_with_retry(
                        order_ticket=12345,
                        deal_ticket=67890,
                        expected_symbol="EURUSD",
                        expected_volume=0.1,
                        max_retries=3,
                    )

        assert "12345" in str(exc_info.value)
        assert "retries" in str(exc_info.value).lower()

    def test_verify_with_retry_uses_exponential_backoff(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_verify_with_retry should use exponential backoff delays."""
        from mt5linux import OrderVerificationResult

        fail_result = OrderVerificationResult(
            verified=False, order_ticket=12345, reason="Not found"
        )
        success_result = OrderVerificationResult(verified=True, order_ticket=12345)

        # Fail 3 times, then succeed
        with patch.object(
            mt5_instance,
            "_query_order_execution",
            side_effect=[fail_result, fail_result, fail_result, success_result],
        ):
            with patch("time.sleep") as mock_sleep:
                mt5_instance._verify_with_retry(
                    order_ticket=12345,
                    deal_ticket=67890,
                    expected_symbol="EURUSD",
                    expected_volume=0.1,
                    max_retries=3,
                    base_delay_ms=100,
                )

        # Check exponential backoff: 100ms, 200ms, 400ms
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == pytest.approx(0.1, rel=0.01)  # 100ms
        assert sleep_calls[1] == pytest.approx(0.2, rel=0.01)  # 200ms
        assert sleep_calls[2] == pytest.approx(0.4, rel=0.01)  # 400ms

    def test_verify_with_retry_caps_delay_at_max(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_verify_with_retry should cap delay at maximum (2000ms)."""
        from mt5linux import OrderVerificationResult

        fail_result = OrderVerificationResult(
            verified=False, order_ticket=12345, reason="Not found"
        )

        with patch.object(
            mt5_instance, "_query_order_execution", return_value=fail_result
        ):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(Exception):  # Will timeout
                    mt5_instance._verify_with_retry(
                        order_ticket=12345,
                        deal_ticket=67890,
                        expected_symbol="EURUSD",
                        expected_volume=0.1,
                        max_retries=10,  # More retries to test cap
                        base_delay_ms=500,  # 500, 1000, 2000, 2000, 2000...
                    )

        # Check that delays are capped at 2s
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        for delay in sleep_calls:
            assert delay <= 2.0  # Max 2 seconds

    def test_verify_with_retry_logs_each_attempt(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_verify_with_retry should log each retry attempt."""
        from mt5linux import OrderVerificationResult

        fail_result = OrderVerificationResult(
            verified=False, order_ticket=12345, reason="Not found"
        )
        success_result = OrderVerificationResult(verified=True, order_ticket=12345)

        with patch.object(
            mt5_instance,
            "_query_order_execution",
            side_effect=[fail_result, success_result],
        ):
            with patch("time.sleep"):
                with patch("mt5linux.logger") as mock_logger:
                    mt5_instance._verify_with_retry(
                        order_ticket=12345,
                        deal_ticket=67890,
                        expected_symbol="EURUSD",
                        expected_volume=0.1,
                    )

        # Verify debug logs were called for retry
        assert mock_logger.debug.called

    def test_verify_with_retry_updates_attempts_count(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_verify_with_retry should update attempts_count in result."""
        from mt5linux import OrderVerificationResult

        fail_result = OrderVerificationResult(
            verified=False, order_ticket=12345, reason="Not found"
        )
        success_result = OrderVerificationResult(
            verified=True, order_ticket=12345, attempts_count=1
        )

        with patch.object(
            mt5_instance,
            "_query_order_execution",
            side_effect=[fail_result, fail_result, success_result],
        ):
            with patch("time.sleep"):
                result = mt5_instance._verify_with_retry(
                    order_ticket=12345,
                    deal_ticket=67890,
                    expected_symbol="EURUSD",
                    expected_volume=0.1,
                )

        # Should be 3 attempts total
        assert result.attempts_count == 3


# =============================================================================
# Task 5: _on_order_submitted() Integration Tests
# =============================================================================
@pytest.mark.unit
class TestOnOrderSubmittedVerification:
    """Test _on_order_submitted integration with verification."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance with mocked connection."""
        import threading

        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            mt5._host = "localhost"
            mt5._port = 18812
            mt5._auto_connect = True
            mt5._lock = threading.Lock()
            mt5._last_order_elapsed_ms = 0.0

            mock_conn = MagicMock()
            mt5._MetaTrader5__conn = mock_conn

            return mt5

    def test_on_order_submitted_calls_verify_with_retry(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_submitted should call _verify_with_retry for verification."""
        from mt5linux import OrderVerificationResult

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        success_verification = OrderVerificationResult(
            verified=True, order_ticket=12345
        )

        with patch.object(
            mt5_instance, "_verify_with_retry", return_value=success_verification
        ) as mock_verify:
            with patch.object(mt5_instance, "_log_verification_result"):
                mt5_instance._on_order_submitted(mock_result)

        mock_verify.assert_called_once()

    def test_on_order_submitted_stores_verification_result(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_submitted should store verification result."""
        from mt5linux import OrderVerificationResult

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        success_verification = OrderVerificationResult(
            verified=True, order_ticket=12345
        )

        with patch.object(
            mt5_instance, "_verify_with_retry", return_value=success_verification
        ):
            with patch.object(mt5_instance, "_log_verification_result"):
                mt5_instance._on_order_submitted(mock_result)

        assert mt5_instance._last_verification_result == success_verification

    def test_on_order_submitted_calls_log_verification_result(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_submitted should call _log_verification_result."""
        from mt5linux import OrderVerificationResult

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        success_verification = OrderVerificationResult(
            verified=True, order_ticket=12345
        )

        with patch.object(
            mt5_instance, "_verify_with_retry", return_value=success_verification
        ):
            with patch.object(mt5_instance, "_log_verification_result") as mock_log:
                mt5_instance._on_order_submitted(mock_result)

        mock_log.assert_called_once_with(success_verification)

    def test_on_order_submitted_calls_on_verification_failed_on_timeout(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_submitted should call _on_verification_failed on timeout."""
        from mt5linux import VerificationTimeoutError

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        with patch.object(
            mt5_instance,
            "_verify_with_retry",
            side_effect=VerificationTimeoutError("Timed out"),
        ):
            with patch.object(mt5_instance, "_on_verification_failed") as mock_failed:
                mt5_instance._on_order_submitted(mock_result)

        mock_failed.assert_called_once_with(mock_result)

    def test_on_order_submitted_clears_verification_result_on_timeout(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_submitted should clear _last_verification_result on timeout."""
        from mt5linux import OrderVerificationResult, VerificationTimeoutError

        # Set a previous verification result
        mt5_instance._last_verification_result = OrderVerificationResult(
            verified=True, order_ticket=99999
        )

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        with patch.object(
            mt5_instance,
            "_verify_with_retry",
            side_effect=VerificationTimeoutError("Timed out"),
        ):
            with patch.object(mt5_instance, "_on_verification_failed"):
                mt5_instance._on_order_submitted(mock_result)

        # Result should be cleared (not stale)
        assert mt5_instance._last_verification_result is None

    def test_on_order_submitted_handles_none_order_ticket(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_submitted should handle None order_ticket gracefully."""
        mock_result = MagicMock()
        mock_result.order = None  # Edge case: order ticket is None
        mock_result.deal = None
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        # Should not raise and should not call verification
        with patch.object(mt5_instance, "_verify_with_retry") as mock_verify:
            with patch("mt5linux.logger"):
                mt5_instance._on_order_submitted(mock_result)

        # Verification should NOT be called when order_ticket is None
        mock_verify.assert_not_called()
        # Result should be None
        assert mt5_instance._last_verification_result is None

    def test_on_order_submitted_updates_last_order_elapsed_ms(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_order_submitted should update _last_order_elapsed_ms to include verification."""
        from mt5linux import OrderVerificationResult

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        success_verification = OrderVerificationResult(
            verified=True, order_ticket=12345, verification_latency_ms=50.0
        )

        with patch.object(
            mt5_instance, "_verify_with_retry", return_value=success_verification
        ):
            with patch.object(mt5_instance, "_log_verification_result"):
                mt5_instance._on_order_submitted(mock_result)

        # _last_order_elapsed_ms should exist
        assert hasattr(mt5_instance, "_last_order_elapsed_ms")


# =============================================================================
# Task 6: Verification Result Logging Tests
# =============================================================================
@pytest.mark.unit
class TestVerificationLogging:
    """Test _log_verification_result method."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            return mt5

    def test_log_verification_result_method_exists(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_log_verification_result method should exist."""
        assert hasattr(mt5_instance, "_log_verification_result")
        assert callable(mt5_instance._log_verification_result)

    def test_log_verification_result_logs_order_ticket(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_log_verification_result should log order_ticket."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, attempts_count=1
        )

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_verification_result(result)

        call_args = str(mock_logger.info.call_args)
        assert "12345" in call_args

    def test_log_verification_result_logs_verified_status(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_log_verification_result should log verified status."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, attempts_count=1
        )

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_verification_result(result)

        call_args = str(mock_logger.info.call_args).lower()
        assert "verif" in call_args or "true" in call_args

    def test_log_verification_result_logs_attempts_count(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_log_verification_result should log attempts_count."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True, order_ticket=12345, attempts_count=3
        )

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_verification_result(result)

        call_args = str(mock_logger.info.call_args)
        assert "3" in call_args or "attempt" in call_args.lower()

    def test_log_verification_result_does_not_log_price(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_log_verification_result must NOT log execution_price (sensitive)."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True,
            order_ticket=12345,
            execution_price=1.12345,
            attempts_count=1,
        )

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_verification_result(result)

        call_args = str(mock_logger.info.call_args)
        assert "1.12345" not in call_args

    def test_log_verification_result_does_not_log_volume(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_log_verification_result must NOT log volume details (sensitive)."""
        from mt5linux import OrderVerificationResult

        result = OrderVerificationResult(
            verified=True,
            order_ticket=12345,
            volume=0.1,
            attempts_count=1,
        )

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._log_verification_result(result)

        call_args = str(mock_logger.info.call_args)
        # Volume 0.1 should not appear in log
        assert "0.1" not in call_args


# =============================================================================
# Task 7: Verification Status Accessor Tests
# =============================================================================
@pytest.mark.unit
class TestGetLastVerificationResult:
    """Test get_last_verification_result accessor method."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            return mt5

    def test_get_last_verification_result_method_exists(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """get_last_verification_result method should exist."""
        assert hasattr(mt5_instance, "get_last_verification_result")
        assert callable(mt5_instance.get_last_verification_result)

    def test_get_last_verification_result_returns_none_initially(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """get_last_verification_result should return None if no verification performed."""
        mt5_instance._last_verification_result = None

        result = mt5_instance.get_last_verification_result()

        assert result is None

    def test_get_last_verification_result_returns_stored_result(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """get_last_verification_result should return stored verification result."""
        from mt5linux import OrderVerificationResult

        stored_result = OrderVerificationResult(verified=True, order_ticket=12345)
        mt5_instance._last_verification_result = stored_result

        result = mt5_instance.get_last_verification_result()

        assert result is stored_result
        assert result.order_ticket == 12345


# =============================================================================
# Task 8: Failure Detection Hook Tests
# =============================================================================
@pytest.mark.unit
class TestOnVerificationFailed:
    """Test _on_verification_failed callback method."""

    @pytest.fixture
    def mt5_instance(self) -> MetaTrader5:
        """Create a MetaTrader5 instance."""
        with patch("mt5linux.MetaTrader5.__init__", return_value=None):
            mt5 = MetaTrader5.__new__(MetaTrader5)
            return mt5

    def test_on_verification_failed_method_exists(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_verification_failed method should exist."""
        assert hasattr(mt5_instance, "_on_verification_failed")
        assert callable(mt5_instance._on_verification_failed)

    def test_on_verification_failed_accepts_result(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_verification_failed should accept order result."""
        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890

        # Should not raise
        mt5_instance._on_verification_failed(mock_result)

    def test_on_verification_failed_logs_failure_context(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """_on_verification_failed should log failure context."""
        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890

        with patch("mt5linux.logger") as mock_logger:
            mt5_instance._on_verification_failed(mock_result)

        # Should log warning or error
        assert mock_logger.warning.called or mock_logger.error.called


# =============================================================================
# Integration Tests
# =============================================================================
@pytest.mark.unit
class TestTradeVerificationIntegration:
    """Integration tests for trade verification flow."""

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
            mt5._last_order_elapsed_ms = 0.0
            mt5._last_verification_result = None

            mock_conn = MagicMock()
            mt5._MetaTrader5__conn = mock_conn

            return mt5

    def test_full_verification_flow_success(self, mt5_instance: MetaTrader5) -> None:
        """Test complete verification flow for successful case."""
        # Setup: Mock a successful order in history
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.return_value = (mock_order,)

        # Create order result
        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        # Execute verification
        with patch("mt5linux.logger"):
            mt5_instance._on_order_submitted(mock_result)

        # Verify result was stored
        assert mt5_instance._last_verification_result is not None
        assert mt5_instance._last_verification_result.verified is True
        assert mt5_instance._last_verification_result.order_ticket == 12345

    def test_full_verification_flow_with_retries(
        self, mt5_instance: MetaTrader5
    ) -> None:
        """Test verification flow with retries before success."""
        # Setup: First call returns None (not found), second returns filled order
        mock_order = MagicMock()
        mock_order.state = 4  # ORDER_STATE_FILLED
        mock_order.symbol = "EURUSD"
        mock_order.volume_initial = 0.1
        mock_order.time_done = 1582303777
        mock_order.price_open = 1.10264

        mt5_instance._MetaTrader5__conn.eval.side_effect = [None, (mock_order,)]

        mock_result = MagicMock()
        mock_result.order = 12345
        mock_result.deal = 67890
        mock_result.request = {"symbol": "EURUSD", "volume": 0.1}

        with patch("mt5linux.logger"):
            with patch("time.sleep"):
                mt5_instance._on_order_submitted(mock_result)

        # Verify result was stored after retry
        assert mt5_instance._last_verification_result is not None
        assert mt5_instance._last_verification_result.verified is True
